from app.api.routes.internal import router as internal_router
from fastapi import FastAPI

from app.api.routes.catalog import router as catalog_router
from app.api.routes.health import router as health_router
from app.core.config import settings

from devsphere_common.logging import configure_logging
from devsphere_common.middleware import (
    install_correlation_id_middleware,
)


configure_logging(settings.log_level)

app = FastAPI(
    title="DevSphere Service Catalog",
    description="Manage developer applications and services.",
    version=settings.app_version,
)

install_correlation_id_middleware(
    app,
    settings.service_name,
)

app.include_router(health_router)
app.include_router(catalog_router)

app.include_router(internal_router)
