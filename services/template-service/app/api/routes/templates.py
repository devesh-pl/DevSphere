"""DevSphere template discovery and project generation APIs."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.generator import (
    TEMPLATES,
    generate_project,
    list_templates,
)


router = APIRouter(
    prefix="/templates",
    tags=["Templates"],
)


class GenerateRequest(BaseModel):
    project_slug: str = Field(
        min_length=3,
        max_length=63,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    )


@router.get("")
def get_templates(
    current_user: dict = Depends(get_current_user),
):
    return {
        "templates": list_templates(),
        "total": len(TEMPLATES),
    }


@router.get("/{template_id}")
def get_template_details(
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    template = TEMPLATES.get(template_id)

    if template is None:
        raise HTTPException(
            status_code=404,
            detail="Template not found",
        )

    return template


@router.post("/{template_id}/generate")
def generate_template(
    template_id: str,
    payload: GenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    if current_user.get("role") not in ("developer", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions",
        )

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
            "Content-Disposition": (
                f'attachment; filename="{payload.project_slug}.zip"'
            ),
            "Cache-Control": "no-store",
        },
    )
