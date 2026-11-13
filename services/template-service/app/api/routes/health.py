"""Template Service health and readiness endpoints."""

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.core.generator import TEMPLATES


router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "template-service",
    }


@router.get("/ready")
def ready():
    root = settings.template_root

    if not root.is_dir():
        raise HTTPException(
            status_code=503,
            detail="Template directory unavailable",
        )

    for template_id in TEMPLATES:
        if not (root / template_id).is_dir():
            raise HTTPException(
                status_code=503,
                detail="Required template unavailable",
            )

    return {
        "status": "ready",
        "service": "template-service",
    }
