from app.api.routes.auth import router as auth_router
import logging

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import settings

from devsphere_common.logging import configure_logging
from devsphere_common.middleware import install_correlation_id_middleware

configure_logging(settings.log_level)
logger = logging.getLogger("devsphere.request")

app = FastAPI(
    title=f"DevSphere {settings.service_name}",
    description="DevSphere microservice backend",
    version=settings.app_version,
)

install_correlation_id_middleware(app, settings.service_name)

app.include_router(health_router)

app.include_router(auth_router)
