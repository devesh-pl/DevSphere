from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=2000)
    repository_url: HttpUrl
    language: str = Field(min_length=1, max_length=50)
    framework: str = Field(min_length=1, max_length=100)


class ServiceResponse(BaseModel):
    id: str
    name: str
    description: str
    repository_url: str
    language: str
    framework: str
    owner_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
