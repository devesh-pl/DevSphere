"""Synchronize DevSphere deployment records with Kubernetes state."""

import logging
import threading

from kubernetes.client.exceptions import ApiException
from sqlalchemy import text

logger = logging.getLogger("devsphere.deployment.reconciler")

INTERVAL_SECONDS = 15


def classify_rollout(deployment, expected_image, expected_replicas):
    """Return (status, error_message), or None if state is inconclusive."""

    spec = deployment.spec
    status = deployment.status
    metadata = deployment.metadata

    desired = spec.replicas or 0
    observed = status.observed_generation or 0
    generation = metadata.generation or 0

    containers = spec.template.spec.containers or []
    actual_image = next(
        (container.image for container in containers
         if container.name == "application"),
        None,
    )

    # Avoid reconciling an older rollout after another API request
    # has changed the desired configuration.
    if (
        actual_image != expected_image
        or desired != expected_replicas
    ):
        return None

    if observed < generation:
        return "deploying", None

    conditions = status.conditions or []

    for condition in conditions:
        if (
            condition.type == "Progressing"
            and condition.status == "False"
            and condition.reason == "ProgressDeadlineExceeded"
        ):
            return "failed", "Kubernetes rollout exceeded its progress deadline"

    ready = status.ready_replicas or 0
    available = status.available_replicas or 0
    updated = status.updated_replicas or 0

    if (
        desired > 0
        and ready >= desired
        and available >= desired
        and updated >= desired
    ):
        return "running", None

    return "deploying", None


def reconcile_once():
    """Reconcile a snapshot of active deployment records."""

    # Import inside the function to avoid circular imports.
    from app.main import (
        NAMESPACE,
        SessionLocal,
        apps_api,
    )

    with SessionLocal() as db:
        rows = db.execute(
            text("""
                SELECT id, name, namespace, image, replicas, status
                FROM deployments
                WHERE status IN ('deploying', 'running')
                  AND name NOT LIKE 'ds-java-%'
                ORDER BY created_at
            """)
        ).mappings().all()

    updated_count = 0

    for row in rows:
        record = dict(row)

        if record["namespace"] != NAMESPACE:
            continue

        try:
            deployment = apps_api.read_namespaced_deployment(
                name=record["name"],
                namespace=NAMESPACE,
                _request_timeout=8,
            )

        except ApiException as error:
            if error.status == 404:
                logger.warning(
                    "Deployment %s is missing from Kubernetes",
                    record["name"],
                )
            else:
                logger.warning(
                    "Cannot inspect deployment %s: %s",
                    record["name"],
                    error,
                )
            continue

        except Exception:
            logger.exception(
                "Kubernetes inspection failed for %s",
                record["name"],
            )
            continue

        result = classify_rollout(
            deployment,
            record["image"],
            record["replicas"],
        )

        if result is None:
            continue

        new_status, error_message = result

        if new_status == record["status"]:
            continue

        # Compare the current row with the previously observed values.
        # This protects changes made concurrently by scale/rollback/delete.
        with SessionLocal.begin() as db:
            changed = db.execute(
                text("""
                    UPDATE deployments
                    SET status = :new_status,
                        error_message = :error_message
                    WHERE id = :id
                      AND namespace = :namespace
                      AND name = :name
                      AND image = :image
                      AND replicas = :replicas
                      AND status = :old_status
                """),
                {
                    "new_status": new_status,
                    "error_message": error_message,
                    "id": record["id"],
                    "namespace": record["namespace"],
                    "name": record["name"],
                    "image": record["image"],
                    "replicas": record["replicas"],
                    "old_status": record["status"],
                },
            ).rowcount

        if changed:
            updated_count += 1
            logger.info(
                "Reconciled %s: %s -> %s",
                record["name"],
                record["status"],
                new_status,
            )

    return updated_count


def run_loop(stop_event):
    logger.info("Deployment reconciler started")

    while not stop_event.is_set():
        try:
            reconcile_once()
        except Exception:
            logger.exception("Deployment reconciliation cycle failed")

        stop_event.wait(INTERVAL_SECONDS)

    logger.info("Deployment reconciler stopped")


def register_reconciler(app):
    """Start and stop the reconciler with the FastAPI application."""

    stop_event = threading.Event()
    worker = None

    @app.on_event("startup")
    def start_reconciler():
        nonlocal worker
        stop_event.clear()
        worker = threading.Thread(
            target=run_loop,
            args=(stop_event,),
            daemon=True,
            name="devsphere-deployment-reconciler",
        )
        worker.start()

    @app.on_event("shutdown")
    def stop_reconciler():
        stop_event.set()
        if worker is not None:
            worker.join(timeout=10)
