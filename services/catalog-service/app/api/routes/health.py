from fastapi import APIRouter, HTTPException

from app.database.session import check_database_connection


router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "catalog-service",
    }


@router.get("/ready")
def ready():
    try:
        check_database_connection()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        )

    return {
        "status": "ready",
        "service": "catalog-service",
    }
