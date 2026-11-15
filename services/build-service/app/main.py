"""DevSphere Build API: durable job submission and tracking."""

import json
import re
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.common import (
    AUTH,
    ORCH,
    SessionLocal,
    cipher,
    get_job,
    row_to_dict,
    runner,
)


app = FastAPI(title="DevSphere Build Service", version="0.3.0")


class BuildCreate(BaseModel):
    operation_id: UUID


def authenticate(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")

    token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(401, "Authentication required")

    try:
        status, user = runner.api(
            "GET",
            AUTH + "/auth/me",
            token=token,
        )
    except Exception:
        raise HTTPException(401, "Invalid credentials")

    if status != 200 or not user.get("id"):
        raise HTTPException(401, "Invalid credentials")

    if user.get("role") not in ("developer", "admin"):
        raise HTTPException(403, "Developer access required")

    return token, user


def owned_job(job_id, user_id):
    with SessionLocal() as db:
        row = db.execute(
            text("""
                SELECT * FROM build_jobs
                WHERE id=:id AND owner_id=:owner
            """),
            {"id": job_id, "owner": user_id},
        ).mappings().first()

    if not row:
        raise HTTPException(404, "Build not found")

    return row_to_dict(row)


@app.get("/health")
def health():
    return {"status": "ok", "service": "build-service"}


@app.get("/ready")
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Build database unavailable")

    return {"status": "ready", "storage": "postgresql"}


@app.post("/builds", status_code=202)
def create_build(
    payload: BuildCreate,
    authorization: str | None = Header(default=None),
):
    token, user = authenticate(authorization)
    operation_id = str(payload.operation_id)

    try:
        status, operation = runner.api(
            "GET",
            f"{ORCH}/operations/{operation_id}",
            token=token,
        )
    except Exception:
        raise HTTPException(404, "Operation not found")

    if status != 200 or operation.get("owner_id") != user["id"]:
        raise HTTPException(404, "Operation not found")

    if (
        operation.get("operation_type") != "provision_project"
        or operation.get("status") != "completed"
    ):
        raise HTTPException(409, "Completed provisioning required")

    try:
        result = json.loads(operation["result"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(409, "Invalid provisioning result")

    if result.get("template_id") != "fastapi-basic":
        raise HTTPException(422, "Only FastAPI templates supported")

    slug = result.get("project_slug", "")

    if (
        not isinstance(slug, str)
        or len(slug) > 40
        or not re.fullmatch(
            r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*",
            slug,
        )
    ):
        raise HTTPException(422, "Invalid project slug")

    job_id = uuid4().hex

    try:
        with SessionLocal.begin() as db:
            db.execute(
                text("""
                    INSERT INTO build_jobs
                    (id, operation_id, owner_id, project_slug,
                     status, token_ciphertext)
                    VALUES
                    (:id, :operation, :owner, :slug,
                     'queued', :token)
                """),
                {
                    "id": job_id,
                    "operation": operation_id,
                    "owner": user["id"],
                    "slug": slug,
                    "token": cipher.encrypt(
                        token.encode()
                    ).decode(),
                },
            )

    except IntegrityError:
        # Preserve the original job for idempotent submissions.
        with SessionLocal() as db:
            row = db.execute(
                text("""
                    SELECT * FROM build_jobs
                    WHERE operation_id=:operation
                      AND owner_id=:owner
                """),
                {
                    "operation": operation_id,
                    "owner": user["id"],
                },
            ).mappings().first()

        if not row:
            raise HTTPException(409, "Build conflict")

        return row_to_dict(row)

    return get_job(job_id)


@app.get("/builds")
def list_builds(
    authorization: str | None = Header(default=None),
):
    _, user = authenticate(authorization)

    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT * FROM build_jobs
                WHERE owner_id=:owner
                ORDER BY created_at DESC
                LIMIT 100
            """),
            {"owner": user["id"]},
        ).mappings().all()

    return [row_to_dict(row) for row in rows]


@app.get("/builds/{job_id}")
def get_build(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    _, user = authenticate(authorization)
    return owned_job(job_id, user["id"])


@app.post("/builds/{job_id}/retry", status_code=202)
def retry_build(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    token, user = authenticate(authorization)

    with SessionLocal.begin() as db:
        row = db.execute(
            text("""
                UPDATE build_jobs
                SET status='queued',
                    token_ciphertext=:token,
                    error_message=NULL,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    updated_at=NOW()
                WHERE id=:id
                  AND owner_id=:owner
                  AND status='failed'
                  AND attempt_count < max_attempts
                RETURNING id
            """),
            {
                "id": job_id,
                "owner": user["id"],
                "token": cipher.encrypt(
                    token.encode()
                ).decode(),
            },
        ).first()

    if not row:
        raise HTTPException(
            409,
            "Build not retryable or attempt limit reached",
        )

    return get_job(job_id)
