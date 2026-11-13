"""Trusted project generation endpoint for the Orchestrator."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.routes.templates import GenerateRequest
from app.core.generator import (
    TEMPLATES,
    generate_project,
)
from app.core.internal_auth import require_internal_service


router = APIRouter(
    prefix="/internal/templates",
    tags=["Internal Templates"],
    dependencies=[Depends(require_internal_service)],
)


@router.post("/{template_id}/generate")
def generate_internal_project(
    template_id: str,
    payload: GenerateRequest,
):
    if template_id not in TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail="Template not found",
        )

    try:
        archive = generate_project(
            template_id,
            payload.project_slug,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=500,
            detail="Template generation failed",
        ) from error

    return StreamingResponse(
        BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="{payload.project_slug}.zip"',
            "Cache-Control": "no-store",
        },
    )
