"""DevSphere local development Build Service."""

import importlib.util
import json
import logging
import re
import threading
import urllib.error
import urllib.request

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[3]

# Reuse the already-tested local Docker/Kind pipeline.
runner_path = ROOT / "scripts/build-and-deploy.py"
spec = importlib.util.spec_from_file_location(
    "devsphere_build_runner", runner_path
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

AUTH = "http://127.0.0.1:8001"
ORCH = "http://127.0.0.1:8004"
DEPLOY = "http://127.0.0.1:8005"

app = FastAPI(
    title="DevSphere Build Service",
    version="0.1.0",
)

logger = logging.getLogger("devsphere.build")

executor = ThreadPoolExecutor(max_workers=1)
jobs = {}
operation_jobs = {}
lock = threading.Lock()


class BuildCreate(BaseModel):
    operation_id: UUID


def request_json(url, token):
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise HTTPException(401, "Invalid credentials")
        if error.code == 404:
            raise HTTPException(404, "Resource not found")
        raise HTTPException(502, "Upstream service error")

    except (urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, "Upstream service unavailable")


def authenticate(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Authentication required")

    user = request_json(AUTH + "/auth/me", token)

    if not user.get("id") or user.get("role") not in (
        "developer", "admin"
    ):
        raise HTTPException(403, "Developer access required")

    return token, user


def update_job(job_id, **changes):
    with lock:
        jobs[job_id].update(changes)


def run_build(job_id, operation_id, slug, token):
    """Run one validated FastAPI build through Docker and Kind."""

    try:
        update_job(job_id, status="building")

        _, archive = runner.api(
            "GET",
            f"{ORCH}/operations/{operation_id}/download",
            token=token,
        )

        if len(archive) > 3 * 1024 * 1024:
            raise ValueError("Project archive exceeds size limit")

        destination = runner.OUTPUT / job_id

        project = runner.extract_project(
            archive, slug, destination
        )

        image = f"devsphere-built/{slug}:{job_id[:8]}"

        runner.build_image(project, image)

        update_job(
            job_id,
            status="deploying",
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
            raise RuntimeError("Deployment request rejected")

        deployment_id = deployment["id"]

        update_job(
            job_id,
            deployment_id=deployment_id,
        )

        ready = runner.wait_for_deployment(
            deployment_id,
            token,
            timeout=180,
        )

        update_job(
            job_id,
            status="completed",
            kubernetes_name=deployment["name"],
            namespace=ready["namespace"],
        )

    except Exception:
        logger.exception("Build failed: %s", job_id)

        update_job(
            job_id,
            status="failed",
            error="Build or deployment failed; inspect service logs",
        )


@app.get("/health")
def health():
    return {"status": "ok", "service": "build-service"}


@app.post("/builds", status_code=202)
def create_build(
    payload: BuildCreate,
    authorization: str | None = Header(default=None),
):
    token, user = authenticate(authorization)
    operation_id = str(payload.operation_id)

    operation = request_json(
        f"{ORCH}/operations/{operation_id}",
        token,
    )

    if operation.get("owner_id") != user["id"]:
        raise HTTPException(404, "Operation not found")

    if (
        operation.get("operation_type") != "provision_project"
        or operation.get("status") != "completed"
    ):
        raise HTTPException(
            409, "A completed provisioning operation is required"
        )

    try:
        request_payload = json.loads(operation["request_payload"])
    except (KeyError, TypeError, ValueError):
        # The public operation response may not expose request_payload.
        request_payload = None

    result = json.loads(operation["result"])

    if result.get("template_id") != "fastapi-basic":
        raise HTTPException(
            422, "This build runner currently supports FastAPI"
        )

    slug = result["project_slug"]

    if not re.fullmatch(
        r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug
    ) or len(slug) > 63:
        raise HTTPException(422, "Invalid project slug")

    with lock:
        previous = operation_jobs.get(operation_id)

        if previous is not None:
            return dict(jobs[previous])

        job_id = uuid4().hex

        job = {
            "id": job_id,
            "operation_id": operation_id,
            "owner_id": user["id"],
            "status": "queued",
            "image": None,
            "deployment_id": None,
            "kubernetes_name": None,
            "namespace": None,
            "error": None,
        }

        jobs[job_id] = job
        operation_jobs[operation_id] = job_id

    executor.submit(
        run_build, job_id, operation_id, slug, token
    )

    return dict(job)


@app.get("/builds")
def list_builds(
    authorization: str | None = Header(default=None),
):
    _, user = authenticate(authorization)

    with lock:
        return [
            dict(job)
            for job in jobs.values()
            if job["owner_id"] == user["id"]
        ]


@app.get("/builds/{job_id}")
def get_build(
    job_id: str,
    authorization: str | None = Header(default=None),
):
    _, user = authenticate(authorization)

    with lock:
        job = jobs.get(job_id)

        if not job or job["owner_id"] != user["id"]:
            raise HTTPException(404, "Build not found")

        return dict(job)
