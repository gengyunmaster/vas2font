import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectMetadataRequest(BaseModel):
    font_family: str
    font_version: str

    @field_validator("font_family")
    @classmethod
    def validate_font_family(cls, value: str) -> str:
        value = value.strip()
        if (
            not value
            or len(value) > 80
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("Font family must contain 1 to 80 printable characters")
        return value

    @field_validator("font_version")
    @classmethod
    def validate_font_version(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"\d+\.\d{1,3}", value):
            raise ValueError("Font version must use a numeric major.minor format")
        if float(value) > 65535.999:
            raise ValueError("Font version is outside the OpenType range")
        return value


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    font_family: str
    font_version: str
    pipeline_version: str
    created_at: datetime
    updated_at: datetime


class ProjectCreatedResponse(ProjectResponse):
    access_code: str


class OpenProjectRequest(BaseModel):
    access_code: str


class MessageResponse(BaseModel):
    message: str
