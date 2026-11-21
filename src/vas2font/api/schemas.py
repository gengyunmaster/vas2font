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


class TemplateRequest(BaseModel):
    name: str
    version: int
    characters: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if (
            not value
            or len(value) > 80
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("Template name must contain 1 to 80 printable characters")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value < 1 or value > 1_000_000:
            raise ValueError("Template version must be between 1 and 1000000")
        return value


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    name: str
    version: int
    built_in: bool
    character_count: int
    characters: str
    created_at: datetime
    updated_at: datetime


class UploadOrderRequest(BaseModel):
    ordered_ids: list[UUID]


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    position: int
    original_filename: str
    file_size_bytes: int
    sha256: str
    vas_version: int
    glyph_count: int
    stroke_count: int
    validation_report: dict
    created_at: datetime
    updated_at: datetime


class GlyphPreviewPath(BaseModel):
    d: str
    stroke_width: float


class GlyphPreview(BaseModel):
    view_box: str
    paths: list[GlyphPreviewPath]


class GlyphInspectionItem(BaseModel):
    character: str
    codepoint: int
    status: str
    source_upload_id: UUID | None = None
    source_filename: str | None = None
    source_position: int | None = None
    template_name: str | None = None
    template_version: int | None = None
    duplicate_count: int = 0
    overridden_upload_ids: list[UUID] = []
    overflow_strokes: int = 0
    preview: GlyphPreview | None = None


class GlyphInspectionResponse(BaseModel):
    items: list[GlyphInspectionItem]
    total: int
    covered: int
    missing: int
    duplicates: int
    offset: int
    limit: int


class GenerationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    progress: int
    stage: str
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    downloaded_at: datetime | None
