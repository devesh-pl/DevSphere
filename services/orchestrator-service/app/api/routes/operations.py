"""Developer-facing operation management endpoints."""

import json
import logging
import os

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.broker import publish_operation
from app.database.session import get_db
from app.models.operation import Operation
from app.schemas.operation import (
    OperationCreate,
    OperationResponse,
)


router = APIRouter(
    prefix="/operations",
    tags=["Operations"],
)

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path(
    os.environ.get("ARTIFACT_DIR", "/app/artifacts")
)


def authorized_operation(
    operation_id: str,
    current_user: dict,
    db: Session,
) -> Operation:
    """Retrieve an operation only if the user is authorized."""

    try:
        normalized_id = str(UUID(operation_id))
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Operation not found",
        )

    operation = db.get(Operation, normalized_id)

    if operation is None:
        raise HTTPException(
            status_code=404,
            detail="Operation not found",
        )

    is_owner = operation.owner_id == current_user["id"]
    is_admin = current_user.get("role") == "admin"

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=404,
            detail="Operation not found",
        )

    return operation


@router.post(
    "",
    response_model=OperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_operation(
    payload: OperationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create and publish an asynchronous operation."""

    if current_user.get("role") not in ("developer", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )

    request_payload = None

    if payload.operation_type == "provision_project":
        request_payload = json.dumps({
            "project_slug": payload.project_slug,
            "template_id": payload.template_id,
            "repository_url": str(payload.repository_url),
        })

    operation = Operation(
        owner_id=current_user["id"],
        operation_type=payload.operation_type,
        request_payload=request_payload,
        status="pending",
    )

    db.add(operation)
    db.commit()
    db.refresh(operation)

    try:
        publish_operation(operation.id)

    except Exception:
        logger.exception(
            "operation_publish_failed",
            extra={
                "service": "orchestrator-service",
            },
        )

        # A network failure may occur after RabbitMQ accepts
        # the message. Preserve the operation for recovery.
        db.refresh(operation)

        if operation.status == "pending":
            operation.error_message = (
                "Queue publication could not be confirmed"
            )
            db.commit()

        raise HTTPException(
            status_code=503,
            detail="Unable to confirm operation publication",
        )

    # The worker may claim or complete the operation immediately.
    # Use a conditional update to avoid overwriting its newer status.
    db.execute(
        update(Operation)
        .where(
            Operation.id == operation.id,
            Operation.status == "pending",
        )
        .values(status="queued")
    )
    db.commit()
    db.refresh(operation)

    logger.info(
        "operation_submitted",
        extra={
            "service": "orchestrator-service",
        },
    )

    return operation


@router.get(
    "",
    response_model=list[OperationResponse],
)
def list_operations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the authenticated developer's latest operations."""

    statement = (
        select(Operation)
        .where(Operation.owner_id == current_user["id"])
        .order_by(Operation.created_at.desc())
        .limit(100)
    )

    return db.scalars(statement).all()


@router.get(
    "/{operation_id}",
    response_model=OperationResponse,
)
def get_operation(
    operation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve the current state of an operation."""

    return authorized_operation(
        operation_id,
        current_user,
        db,
    )


@router.get("/{operation_id}/download")
def download_project(
    operation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download a successfully generated project ZIP."""

    operation = authorized_operation(
        operation_id,
        current_user,
        db,
    )

    if (
        operation.operation_type != "provision_project"
        or operation.status != "completed"
        or not operation.result
    ):
        raise HTTPException(
            status_code=409,
            detail="Project artifact is not available",
        )

    try:
        result = json.loads(operation.result)
        project_slug = result["project_slug"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="Invalid operation result",
        )

    # The path is derived from the trusted database operation ID.
    # Clients cannot supply arbitrary filesystem paths.
    archive_path = ARTIFACT_DIR / f"{operation.id}.zip"

    if not archive_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Generated archive not found",
        )

    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=f"{project_slug}.zip",
        headers={
            "Cache-Control": "no-store",
        },
    )
