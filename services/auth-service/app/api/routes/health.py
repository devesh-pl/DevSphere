import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.database.session import check_database_connection


router = APIRouter()

logger = logging.getLogger("devsphere.readiness")


@router.get("/health")
def health_check():

    return {
        "status": "ok",
        "service": settings.service_name,
    }


@router.get("/ready")
def readiness_check():

    if settings.database_required:

        try:

            check_database_connection()

        except Exception:

            logger.warning(
                "readiness_check_failed",
                exc_info=True,
                extra={
                    "service": settings.service_name
                },
            )

            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": settings.service_name,
                    "reason": "database_unavailable",
                },
            )

    return {
        "status": "ready",
        "service": settings.service_name,
    }