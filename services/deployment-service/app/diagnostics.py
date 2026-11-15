"""Read-only Kubernetes diagnostics for owned deployments."""

from fastapi import APIRouter, Depends, HTTPException, Query
from kubernetes.client.exceptions import ApiException
from sqlalchemy.orm import Session

from app.main import (
    NAMESPACE,
    core_api,
    current_user,
    get_db,
    get_owned_record,
)

router = APIRouter(tags=["Deployment Diagnostics"])


def owned_active_deployment(deployment_id, user, db):
    record = get_owned_record(db, deployment_id, user)

    if record["status"] in ("deleted", "failed"):
        raise HTTPException(
            status_code=409,
            detail="Deployment is not active",
        )

    return record


def get_pods(record):
    try:
        return core_api.list_namespaced_pod(
            namespace=NAMESPACE,
            label_selector=f"app={record['name']}",
            limit=50,
        ).items
    except ApiException:
        raise HTTPException(
            status_code=502,
            detail="Kubernetes pod lookup failed",
        )


@router.get("/deployments/{deployment_id}/pods")
def list_deployment_pods(
    deployment_id: str,
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = owned_active_deployment(deployment_id, user, db)
    pods = get_pods(record)

    result = []

    for pod in pods:
        statuses = pod.status.container_statuses or []

        result.append({
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "ready": bool(statuses) and all(
                status.ready for status in statuses
            ),
            "restarts": sum(
                status.restart_count for status in statuses
            ),
            "containers": [
                {
                    "name": status.name,
                    "ready": status.ready,
                    "restart_count": status.restart_count,
                }
                for status in statuses
            ],
        })

    return {
        "deployment_id": record["id"],
        "pods": result,
    }


@router.get("/deployments/{deployment_id}/logs")
def deployment_logs(
    deployment_id: str,
    tail_lines: int = Query(default=100, ge=1, le=200),
    user: dict = Depends(current_user),
    db: Session = Depends(get_db),
):
    record = owned_active_deployment(deployment_id, user, db)
    pods = get_pods(record)

    if not pods:
        return {
            "deployment_id": record["id"],
            "pod": None,
            "logs": "No pods found for this deployment.",
        }

    # Prefer a running pod.
    pods.sort(
        key=lambda pod: (
            pod.status.phase != "Running",
            pod.metadata.name,
        )
    )

    pod_name = pods[0].metadata.name

    try:
        output = core_api.read_namespaced_pod_log(
            name=pod_name,
            namespace=NAMESPACE,
            container="application",
            tail_lines=tail_lines,
            timestamps=True,
        )
    except ApiException as error:
        if error.status in (400, 404):
            raise HTTPException(
                status_code=409,
                detail="Pod logs are not available yet",
            )

        raise HTTPException(
            status_code=502,
            detail="Kubernetes log retrieval failed",
        )

    return {
        "deployment_id": record["id"],
        "pod": pod_name,
        "logs": str(output)[-40000:],
    }
