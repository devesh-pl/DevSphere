from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.session import get_db
from app.models.service import CatalogService
from app.schemas.service import ServiceCreate, ServiceResponse


router = APIRouter(
    prefix="/catalog/services",
    tags=["Service Catalog"],
)


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    payload: ServiceCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user["role"] not in ("developer", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )

    service = CatalogService(
        name=payload.name,
        description=payload.description,
        repository_url=str(payload.repository_url),
        language=payload.language,
        framework=payload.framework,
        owner_id=current_user["id"],
    )

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


@router.get("", response_model=list[ServiceResponse])
def list_services(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(CatalogService).order_by(
        CatalogService.created_at.desc()
    )

    return db.scalars(statement).all()


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = db.get(CatalogService, service_id)

    if service is None:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = db.get(CatalogService, service_id)

    if service is None:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    if (
        service.owner_id != current_user["id"]
        and current_user["role"] != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="Only the owner or an administrator can delete this service",
        )

    db.delete(service)
    db.commit()
