"""DevSphere independent PostgreSQL build worker."""

import logging
import os
import shutil
import threading
import time

from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import InvalidToken
from sqlalchemy import text

from app.common import (
    DEPLOY,
    ORCH,
    SessionLocal,
    cipher,
    runner,
    utc_now,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

log = logging.getLogger("devsphere.build.worker")

WORKER_ID = str(uuid4())
LEASE_SECONDS = 90
HEARTBEAT_SECONDS = 10
POLL_SECONDS = 2


def recover_expired():
    """Requeue interrupted jobs or fail exhausted jobs."""

    with SessionLocal.begin() as db:
        exhausted = db.execute(
            text("""
                UPDATE build_jobs
                SET status='failed',
                    error_message='Worker lease expired; retry limit reached',
                    token_ciphertext=NULL,
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    updated_at=NOW()
                WHERE status IN ('building', 'deploying')
                  AND lease_expires_at < NOW()
                  AND attempt_count >= max_attempts
                RETURNING id
            """)
        ).all()

        recovered = db.execute(
            text("""
                UPDATE build_jobs
                SET status='queued',
                    error_message='Resuming interrupted build',
                    lease_owner=NULL,
                    lease_expires_at=NULL,
                    updated_at=NOW()
                WHERE status IN ('building', 'deploying')
                  AND lease_expires_at < NOW()
                  AND attempt_count < max_attempts
                RETURNING id
            """)
        ).all()

    for row in recovered:
        log.warning("Recovered interrupted build: %s", row.id)

    for row in exhausted:
        log.error("Build exhausted retries: %s", row.id)


def claim_job():
    """Atomically claim one eligible queued job."""

    with SessionLocal.begin() as db:
        row = db.execute(
            text("""
                SELECT *
                FROM build_jobs
                WHERE status='queued'
                  AND attempt_count < max_attempts
                  AND token_ciphertext IS NOT NULL
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """)
        ).mappings().first()

        if not row:
            return None

        job = dict(row)

        db.execute(
            text("""
                UPDATE build_jobs
                SET status='building',
                    attempt_count=attempt_count+1,
                    lease_owner=:worker,
                    lease_expires_at=NOW() + INTERVAL '90 seconds',
                    last_heartbeat_at=NOW(),
                    error_message=NULL,
                    updated_at=NOW()
                WHERE id=:id
            """),
            {"id": job["id"], "worker": WORKER_ID},
        )

    log.info("Claimed job %s", job["id"])
    return job


def heartbeat(job_id, stopped):
    """Extend the lease while this worker is processing the job."""

    while not stopped.wait(HEARTBEAT_SECONDS):
        try:
            with SessionLocal.begin() as db:
                result = db.execute(
                    text("""
                        UPDATE build_jobs
                        SET lease_expires_at=
                                NOW() + INTERVAL '90 seconds',
                            last_heartbeat_at=NOW()
                        WHERE id=:id
                          AND lease_owner=:worker
                          AND status IN ('building', 'deploying')
                        RETURNING id
                    """),
                    {"id": job_id, "worker": WORKER_ID},
                ).first()

            if result is None:
                log.error("Lease ownership lost: %s", job_id)
                return

        except Exception:
            log.exception("Heartbeat failed: %s", job_id)


def update_owned(job_id, status, **fields):
    allowed = {
        "image",
        "deployment_id",
        "kubernetes_name",
        "namespace",
        "error_message",
        "token_ciphertext",
    }

    if not set(fields).issubset(allowed):
        raise ValueError("Invalid job update")

    assignments = ["status=:status", "updated_at=NOW()"]
    assignments.extend(f"{key}=:{key}" for key in fields)

    values = {
        "id": job_id,
        "worker": WORKER_ID,
        "status": status,
        **fields,
    }

    with SessionLocal.begin() as db:
        result = db.execute(
            text(
                "UPDATE build_jobs SET "
                + ", ".join(assignments)
                + """
                  WHERE id=:id
                    AND lease_owner=:worker
                    AND status IN ('building', 'deploying')
                    AND lease_expires_at > NOW()
                  RETURNING id
                """
            ),
            values,
        ).first()

    if result is None:
        raise RuntimeError("Worker no longer owns this build")


def execute(job):
    job_id = job["id"]

    try:
        token = cipher.decrypt(
            job["token_ciphertext"].encode()
        ).decode()
    except InvalidToken:
        raise RuntimeError("Unable to decrypt build credential")

    slug = job["project_slug"]
    operation_id = job["operation_id"]

    # Use any previously recorded deployment rather than creating
    # another one after recovery.
    deployment_id = job.get("deployment_id")
    kubernetes_name = job.get("kubernetes_name")

    if not deployment_id:
        _, archive = runner.api(
            "GET",
            f"{ORCH}/operations/{operation_id}/download",
            token=token,
        )

        if not isinstance(archive, bytes):
            raise RuntimeError("Expected project ZIP")

        if len(archive) > 3 * 1024 * 1024:
            raise RuntimeError("Project archive too large")

        destination = runner.OUTPUT / job_id

        if destination.exists():
            shutil.rmtree(destination)

        project = runner.extract_project(
            archive, slug, destination
        )

        image = f"devsphere-built/{slug}:{job_id[:8]}"

        # Builds from the local image; Kind receives the result.
        runner.build_image(project, image)

        update_owned(
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
            raise RuntimeError("Deployment API rejected request")

        deployment_id = deployment["id"]
        kubernetes_name = deployment["name"]

        update_owned(
            job_id,
            "deploying",
            deployment_id=deployment_id,
            kubernetes_name=kubernetes_name,
        )

    ready = runner.wait_for_deployment(
        deployment_id,
        token,
        timeout=180,
    )

    update_owned(
        job_id,
        "completed",
        namespace=ready["namespace"],
        token_ciphertext=None,
    )

    log.info("Build completed: %s", job_id)


def process_job(job):
    job_id = job["id"]
    stopped = threading.Event()

    monitor = threading.Thread(
        target=heartbeat,
        args=(job_id, stopped),
        daemon=True,
    )
    monitor.start()

    try:
        execute(job)

    except Exception as exc:
        log.exception("Build failed: %s", job_id)

        try:
            update_owned(
                job_id,
                "failed",
                error_message=type(exc).__name__,
                token_ciphertext=None,
            )
        except Exception:
            log.exception("Could not record build failure")

    finally:
        stopped.set()
        monitor.join(timeout=HEARTBEAT_SECONDS + 2)


def main():
    log.info("Build worker started: %s", WORKER_ID)

    while True:
        try:
            recover_expired()

            job = claim_job()

            if job:
                process_job(job)
            else:
                time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            log.info("Build worker stopping")
            return

        except Exception:
            log.exception("Worker polling error")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
