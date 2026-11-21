import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, and_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from vas2font.api.db import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    access_code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    font_family: Mapped[str] = mapped_column(String(80))
    font_version: Mapped[str] = mapped_column(String(20))
    pipeline_version: Mapped[str] = mapped_column(String(30), default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TemplateRecord(Base):
    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    layout_version: Mapped[str] = mapped_column(String(30), default="1")
    reference_font_version: Mapped[str] = mapped_column(
        String(80), default="noto-sans-sc-1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadRecord(Base):
    __tablename__ = "uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    template_id: Mapped[UUID] = mapped_column(ForeignKey("templates.id"))
    position: Mapped[int] = mapped_column(Integer)
    notebook: Mapped[dict[str, Any]] = mapped_column(JSONB)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    vas_version: Mapped[int] = mapped_column(Integer)
    glyph_count: Mapped[int] = mapped_column(Integer)
    stroke_count: Mapped[int] = mapped_column(Integer)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "ix_builtin_templates_name_version_active",
    TemplateRecord.name,
    TemplateRecord.version,
    unique=True,
    postgresql_where=and_(
        TemplateRecord.project_id.is_(None), TemplateRecord.deleted_at.is_(None)
    ),
)
Index(
    "ix_custom_templates_project_name_version_active",
    TemplateRecord.project_id,
    TemplateRecord.name,
    TemplateRecord.version,
    unique=True,
    postgresql_where=and_(
        TemplateRecord.project_id.is_not(None), TemplateRecord.deleted_at.is_(None)
    ),
)
Index(
    "ix_uploads_project_position_active",
    UploadRecord.project_id,
    UploadRecord.position,
    unique=True,
    postgresql_where=UploadRecord.deleted_at.is_(None),
)
Index(
    "ix_uploads_template_active",
    UploadRecord.template_id,
    postgresql_where=UploadRecord.deleted_at.is_(None),
)
