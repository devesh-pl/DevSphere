"""Request and response schemas for DevSphere operations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class OperationCreate(BaseModel):
    operation_type: Literal["ping", "provision_project"]

    project_slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=63,
        pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$",
    )

    template_id: Literal["fastapi-basic", "express-basic"] | None = None

    repository_url: HttpUrl | None = None

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation_type == "provision_project":
            if not all((
                self.project_slug,
                self.template_id,
                self.repository_url,
            )):
                raise ValueError(
                    "project_slug, template_id and repository_url are required"
                )

        elif any((
            self.project_slug,
            self.template_id,
            self.repository_url,
        )):
            raise ValueError(
                "Ping operations do not accept project details"
            )

        return self


class OperationResponse(BaseModel):
    id: str
    owner_id: str
    operation_type: str
    status: str
    result: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
