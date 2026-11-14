"""DevSphere Build Service: PostgreSQL-backed local prototype."""

import importlib.util
import json
import logging
import re
import threading

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

import os


ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env.build.local")

DATABASE_URL = os.environ["BUILD_DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
)

SessionLocal = sessionmaker(bind=engine)

runner_path = ROOT / "scripts/build-and-deploy.py"
spec = importlib.util.spec_from_file_location(
    "devsphere_build_runner", runner_path
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

AUTH = "http://127.0.0.1:8001"
ORCH = "http://127.0.0.1:8004"
DEPLOY = "http://127.0.0.1:8005"

app = FastAPI(title="DevSphere Build Service", version="0.2.0")
logger = logging.getLogger("devsphere.build")

executor = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
active_jobs = set()


class BuildCreate(BaseModel):
    operation_id: UUID


def utc_now():
    return datetime.now(timezone.utc)


def row_to_dict(row):
    if row is None:
        return None

    item = dict(row)

    if "error_message" in item:
        item["error"] = item["error_message"]

    for key in ("created_at", "updated_at", "lease_expires_at"):
        if item.get(key) is not None:
            item[key] = item[key].isoformat()

    return item


def get_record(job_id):
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT * FROM build_jobs WHERE id=:id"),
            {"id": job_id},
        ).mappings().first()

        return row_to_dict(row)


def update_job(job_id, status, **fields):
    allowed = {
        "image", "deployment_id", "kubernetes_name",
        "namespace", "error_message", "lease_expires_at",
        "last_heartbeat_at",
    }

    if not set(fields).issubset(allowed):
        raise ValueError("Unsupported update field")

    values = {"id": job_id, "status": status, **fields}

    assignments = ["status=:status", "updated_at=NOW()"]
    assignments.extend(f"{key}=:{key}" for key in fields)

    with SessionLocal.begin() as db:
        db.execute(
            text(
                "UPDATE build_jobs SET "
                + ", ".join(assignments)
                + " WHERE id=:id"
            ),
            values,
        )


def authenticate(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        _, user = runner.api(
            "GET",
            AUTH + "/auth/me",
            token=token,
        )
    except Exception:
        raise HTTPException(401, "Invalid credentials")

    if not user.get("id") or user.get("role") not in (
        "developer", "admin"
    ):
        raise HTTPException(403, "Developer access required")

    return token, user


def run_build(job_id, operation_id, slug, token):
    with lock:
        if job_id in active_jobs:
            return
        active_jobs.add(job_id)

    try:
        with SessionLocal.begin() as db:
            claimed = db.execute(
                text("""
                    UPDATE build_jobs
                    SET status='building',
                        attempt_count=attempt_count+1,
                        error_message=NULL,
                        updated_at=NOW()
                    WHERE id=:id
                      AND status='queued'
                      AND attempt_count < max_attempts
                    RETURNING id
                """),
                {"id": job_id},
            ).first()

        if not claimed:
            return

        _, archive = runner.api(
            "GET",
            f"{ORCH}/operations/{operation_id}/download",
            token=token,
        )

        if not isinstance(archive, bytes):
            raise RuntimeError("Expected ZIP archive")

        if len(archive) > 3 * 1024 * 1024:
            raise ValueError("Archive exceeds 3 MB limit")

        destination = runner.OUTPUT / job_id

        if destination.exists():
            import shutil
            shutil.rmtree(destination)

        project = runner.extract_project(
            archive, slug, destination
        )

        image = f"devsphere-built/{slug}:{job_id[:8]}"

        runner.build_image(project, image)

        update_job(
            job_id,
            "deploying",
            image=image,
        )

        status, deployment = runner.api(
            "POST",
            DEPLOY + "/deployments",
            {
                "name": slug,
                "image": image,
                "container_port": 8000,
                "replicas": 1,
            },
            token,
        )

        if status != 201:
            raise RuntimeError(f"Deployment rejected: {deployment}")

        deployment_id = deployment["id"]

        update_job(
            job_id,
            "deploying",
            deployment_id=deployment_id,
        )

        ready = runner.wait_for_deployment(
            deployment_id, token, timeout=180
        )

        update_job(
            job_id,
            "completed",
            kubernetes_name=deployment["name"],
            namespace=ready["namespace"],
        )

        logger.info("Build completed: %s", job_id)

    except Exception as exc:
        logger.exception("Build failed: %s", job_id)

        # Limit the message length and avoid storing traceback details.
        update_job(
            job_id,
            "failed",
            error_message=type(exc).__name__,
        )

    finally:
        with lock:
            active_jobs.discard(job_id)


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
    except (TypeError, KeyError, ValueError):
        raise HTTPException(409, "Invalid provisioning result")

    if result.get("template_id") != "fastapi-basic":
        raise HTTPException(422, "Only FastAPI templates supported")

    slug = result.get("project_slug", "")

    if (
        not re.fullmatch(
            r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug
        )
        or len(slug) > 63
    ):
        raise HTTPException(422, "Invalid project slug")

    job_id = uuid4().hex

    try:
        with SessionLocal.begin() as db:
            db.execute(
                text("""
                    INSERT INTO build_jobs
                    (id, operation_id, owner_id, project_slug, status)
                    VALUES (:id, :operation, :owner, :slug, 'queued')
                """),
                {
                    "id": job_id,
                    "operation": operation_id,
                    "owner": user["id"],
                    "slug": slug,
                },
            )

    except IntegrityError:
        with SessionLocal() as db:
            row = db.execute(
                text("""
                    SELECT * FROM build_jobs
                    WHERE operation_id=:operation AND owner_id=:owner
                """),
                {
                    "operation": operation_id,
                    "owner": user["id"],
                },
            ).mappings().first()

        if not row:
            raise HTTPException(409, "Build operation conflict")

        return row_to_dict(row)

    executor.submit(
        run_build, job_id, operation_id, slug, token
    )

    return get_record(job_id)


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

    record = get_record(job_id)

    if not record or record["owner_id"] != user["id"]:
        raise HTTPException(404, "Build not found")

    return record


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
                    error_message=NULL,
                    updated_at=NOW()
                WHERE id=:id
                  AND owner_id=:owner
                  AND status='failed'
                  AND attempt_count < max_attempts
                RETURNING operation_id, project_slug
            """),
            {"id": job_id, "owner": user["id"]},
        ).first()

    if not row:
        raise HTTPException(
            409,
            "Build not retryable, not owned, or attempt limit reached",
        )

    executor.submit(
        run_build, job_id, row.operation_id,
        row.project_slug, token
    )

    return get_record(job_id)
