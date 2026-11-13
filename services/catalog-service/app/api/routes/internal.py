"""Trusted application registration from the Orchestrator."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.internal_auth import require_internal_service
from app.database.session import get_db
from app.models.service import CatalogService
from app.schemas.service import ServiceResponse


router = APIRouter(
    prefix="/internal/catalog",
    tags=["Internal Catalog"],
    dependencies=[Depends(require_internal_service)],
)


class ProvisionedServiceCreate(BaseModel):
    operation_id: UUID
    owner_id: UUID
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=2000)
    repository_url: HttpUrl
    language: str = Field(min_length=1, max_length=50)
    framework: str = Field(min_length=1, max_length=100)


@router.post("/services", response_model=ServiceResponse)
def register_provisioned_service(
    payload: ProvisionedServiceCreate,
    db: Session = Depends(get_db),
):
    operation_id = str(payload.operation_id)

    existing = db.scalar(
        select(CatalogService).where(
            CatalogService.provisioning_operation_id == operation_id
        )
    )

    if existing is not None:
        return existing

    service = CatalogService(
        name=payload.name,
        description=payload.description,
        repository_url=str(payload.repository_url),
        language=payload.language,
        framework=payload.framework,
        owner_id=str(payload.owner_id),
        provisioning_operation_id=operation_id,
    )

    db.add(service)

    try:
        db.commit()
        db.refresh(service)
        return service

    except IntegrityError:
        db.rollback()

        # Another worker may already have created this operation.
        existing = db.scalar(
            select(CatalogService).where(
                CatalogService.provisioning_operation_id == operation_id
            )
        )

        if existing is not None:
            return existing

        # An unrelated database constraint failed.
        raise
