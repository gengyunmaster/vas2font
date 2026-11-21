from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord, TemplateRecord, UploadRecord, utc_now
from vas2font.extract import ExtractionResult, extract_handwriting
from vas2font.template import template_from_manifest
from vas2font.vas import Notebook, parse_notebook


def validate_notebook(
    data: object,
    template_record: TemplateRecord,
) -> tuple[Notebook, ExtractionResult, dict[str, object]]:
    try:
        notebook = parse_notebook(data)
        template = template_from_manifest(template_record.manifest)
        extraction = extract_handwriting(notebook, template)
    except (TypeError, ValueError) as error:
        raise ApiError(422, "invalid_notebook", str(error)) from error
    report = {
        "missing_characters": list(extraction.missing_characters),
        "overflow_strokes": extraction.overflow_strokes,
        "page_count": len(notebook.pages),
    }
    if not extraction.glyphs:
        raise ApiError(
            422,
            "empty_handwriting",
            "No usable handwriting was found for the selected template",
            report,
        )
    return notebook, extraction, report


async def active_uploads(
    session: AsyncSession,
    project_id: UUID,
) -> list[UploadRecord]:
    result = await session.scalars(
        select(UploadRecord)
        .where(UploadRecord.project_id == project_id, UploadRecord.deleted_at.is_(None))
        .order_by(UploadRecord.position)
    )
    return list(result)


async def apply_upload_order(
    session: AsyncSession,
    uploads: Sequence[UploadRecord],
) -> None:
    for upload in uploads:
        upload.position = -upload.position
    await session.flush()
    for index, upload in enumerate(uploads, start=1):
        upload.position = index
        upload.updated_at = utc_now()
    await session.flush()


async def place_new_upload(
    session: AsyncSession,
    project: ProjectRecord,
    upload: UploadRecord,
) -> None:
    uploads = await active_uploads(session, project.id)
    await apply_upload_order(session, uploads)
    upload.position = 1
    session.add(upload)
    for index, existing in enumerate(uploads, start=2):
        existing.position = index
    project.updated_at = utc_now()
    await session.commit()


def merge_upload_glyphs(uploads: Sequence[UploadRecord]) -> ExtractionResult:
    merged = {}
    overflow_strokes = 0
    for upload in sorted(uploads, key=lambda item: item.position):
        notebook = parse_notebook(upload.notebook)
        template = template_from_manifest(upload.template.manifest)
        extraction = extract_handwriting(notebook, template)
        overflow_strokes += extraction.overflow_strokes
        for glyph in extraction.glyphs:
            if glyph.character not in merged:
                merged[glyph.character] = glyph
    glyphs = tuple(merged[character] for character in sorted(merged))
    return ExtractionResult(glyphs, (), overflow_strokes)
