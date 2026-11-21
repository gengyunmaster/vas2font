import hashlib
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import or_, select

from vas2font.api.config import get_settings
from vas2font.api.dependencies import ProjectDependency, SessionDependency
from vas2font.api.errors import ApiError
from vas2font.api.models import TemplateRecord, UploadRecord, utc_now
from vas2font.api.schemas import MessageResponse, UploadOrderRequest, UploadResponse
from vas2font.api.upload_service import (
    active_uploads,
    apply_upload_order,
    place_new_upload,
    validate_notebook,
)

router = APIRouter(prefix="/api")
settings = get_settings()


@router.get("/projects/{project_id}/uploads", response_model=list[UploadResponse])
async def list_uploads(
    project: ProjectDependency,
    session: SessionDependency,
) -> list[UploadRecord]:
    return await active_uploads(session, project.id)


@router.post(
    "/projects/{project_id}/uploads",
    response_model=UploadResponse,
    status_code=201,
)
async def create_upload(
    project: ProjectDependency,
    session: SessionDependency,
    file: Annotated[UploadFile, File(...)],
    template_id: Annotated[UUID, Form(...)],
) -> UploadResponse:
    filename = re.split(r"[\\/]", file.filename or "notebook.json")[-1][:255]
    if not filename.lower().endswith(".json"):
        raise ApiError(
            415, "json_required", "Only vas JSON notebook files are accepted"
        )
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise ApiError(
            413, "upload_too_large", "The notebook exceeds the upload size limit"
        )
    try:
        data = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiError(
            422, "invalid_json", "The uploaded file is not valid UTF-8 JSON"
        ) from error
    template = await session.scalar(
        select(TemplateRecord).where(
            TemplateRecord.id == template_id,
            TemplateRecord.deleted_at.is_(None),
            or_(
                TemplateRecord.project_id.is_(None),
                TemplateRecord.project_id == project.id,
            ),
        )
    )
    if template is None:
        raise ApiError(
            404, "template_not_found", "The selected template is not available"
        )
    notebook, extraction, report = validate_notebook(data, template)
    upload = UploadRecord(
        project_id=project.id,
        template_id=template.id,
        notebook=data,
        original_filename=filename or "notebook.json",
        file_size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        vas_version=data["version"],
        glyph_count=len(extraction.glyphs),
        stroke_count=sum(len(page.strokes) for page in notebook.pages),
        validation_report=report,
    )
    await place_new_upload(session, project, upload)
    return upload


@router.put("/projects/{project_id}/upload-order", response_model=list[UploadResponse])
async def reorder_uploads(
    body: UploadOrderRequest,
    project: ProjectDependency,
    session: SessionDependency,
) -> list[UploadRecord]:
    uploads = await active_uploads(session, project.id)
    if len(body.ordered_ids) != len(set(body.ordered_ids)):
        raise ApiError(422, "duplicate_upload_ids", "Upload IDs must be unique")
    by_id = {upload.id: upload for upload in uploads}
    if set(body.ordered_ids) != set(by_id):
        raise ApiError(
            409,
            "upload_order_mismatch",
            "The order must contain every active upload exactly once",
        )
    ordered = [by_id[upload_id] for upload_id in body.ordered_ids]
    await apply_upload_order(session, ordered)
    project.updated_at = utc_now()
    await session.commit()
    return ordered


@router.delete(
    "/projects/{project_id}/uploads/{upload_id}", response_model=MessageResponse
)
async def delete_upload(
    project: ProjectDependency,
    upload_id: UUID,
    session: SessionDependency,
) -> MessageResponse:
    upload = await session.scalar(
        select(UploadRecord).where(
            UploadRecord.id == upload_id,
            UploadRecord.project_id == project.id,
            UploadRecord.deleted_at.is_(None),
        )
    )
    if upload is None:
        raise ApiError(404, "upload_not_found", "The upload was not found")
    upload.deleted_at = utc_now()
    upload.updated_at = upload.deleted_at
    await session.flush()
    uploads = await active_uploads(session, project.id)
    await apply_upload_order(session, uploads)
    project.updated_at = utc_now()
    await session.commit()
    return MessageResponse(message="Upload deleted")
