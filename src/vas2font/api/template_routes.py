from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response
from sqlalchemy import or_, select

from vas2font.api.dependencies import (
    ProjectDependency,
    SessionDependency,
    authorized_project,
)
from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord, TemplateRecord, UploadRecord, utc_now
from vas2font.api.schemas import MessageResponse, TemplateRequest, TemplateResponse
from vas2font.api.template_service import (
    custom_manifest,
    download_name,
    normalize_characters,
)
from vas2font.pdf import render_template_pdf
from vas2font.template import template_from_manifest

router = APIRouter(prefix="/api")


@router.get("/templates", response_model=list[TemplateResponse])
async def list_builtin_templates(
    session: SessionDependency,
) -> list[TemplateRecord]:
    result = await session.scalars(
        select(TemplateRecord)
        .where(TemplateRecord.project_id.is_(None), TemplateRecord.deleted_at.is_(None))
        .order_by(TemplateRecord.name, TemplateRecord.version)
    )
    return list(result)


@router.get("/projects/{project_id}/templates", response_model=list[TemplateResponse])
async def list_project_templates(
    project: ProjectDependency,
    session: SessionDependency,
) -> list[TemplateRecord]:
    result = await session.scalars(
        select(TemplateRecord)
        .where(
            or_(
                TemplateRecord.project_id.is_(None),
                TemplateRecord.project_id == project.id,
            ),
            TemplateRecord.deleted_at.is_(None),
        )
        .order_by(
            TemplateRecord.project_id.is_not(None),
            TemplateRecord.name,
            TemplateRecord.version,
        )
    )
    return list(result)


async def project_template(
    project: ProjectRecord,
    template_id: UUID,
    session: SessionDependency,
) -> TemplateRecord:
    template = await session.scalar(
        select(TemplateRecord).where(
            TemplateRecord.id == template_id,
            TemplateRecord.project_id == project.id,
            TemplateRecord.deleted_at.is_(None),
        )
    )
    if template is None:
        raise ApiError(404, "template_not_found", "The template was not found")
    return template


async def ensure_no_active_references(
    template: TemplateRecord, session: SessionDependency
) -> None:
    upload_id = await session.scalar(
        select(UploadRecord.id)
        .where(
            UploadRecord.template_id == template.id,
            UploadRecord.deleted_at.is_(None),
        )
        .limit(1)
    )
    if upload_id is not None:
        raise ApiError(
            409,
            "template_has_active_uploads",
            "This template is referenced by active uploads; create a new version instead",
        )


@router.post(
    "/projects/{project_id}/templates",
    response_model=TemplateResponse,
    status_code=201,
)
async def create_template(
    body: TemplateRequest,
    project: ProjectDependency,
    session: SessionDependency,
) -> TemplateRecord:
    characters = normalize_characters(body.characters)
    duplicate = await session.scalar(
        select(TemplateRecord.id).where(
            TemplateRecord.project_id == project.id,
            TemplateRecord.name == body.name,
            TemplateRecord.version == body.version,
            TemplateRecord.deleted_at.is_(None),
        )
    )
    if duplicate is not None:
        raise ApiError(
            409, "template_exists", "This template name and version already exist"
        )
    template = TemplateRecord(
        project_id=project.id,
        name=body.name,
        version=body.version,
        manifest=custom_manifest(body.name, body.version, characters),
    )
    session.add(template)
    project.updated_at = utc_now()
    await session.commit()
    return template


@router.patch(
    "/projects/{project_id}/templates/{template_id}", response_model=TemplateResponse
)
async def edit_template(
    body: TemplateRequest,
    project: ProjectDependency,
    template_id: UUID,
    session: SessionDependency,
) -> TemplateRecord:
    template = await project_template(project, template_id, session)
    await ensure_no_active_references(template, session)
    characters = normalize_characters(body.characters)
    duplicate = await session.scalar(
        select(TemplateRecord.id).where(
            TemplateRecord.project_id == project.id,
            TemplateRecord.name == body.name,
            TemplateRecord.version == body.version,
            TemplateRecord.deleted_at.is_(None),
            TemplateRecord.id != template.id,
        )
    )
    if duplicate is not None:
        raise ApiError(
            409, "template_exists", "This template name and version already exist"
        )
    template.name = body.name
    template.version = body.version
    template.manifest = custom_manifest(body.name, body.version, characters)
    template.updated_at = utc_now()
    project.updated_at = utc_now()
    await session.commit()
    return template


@router.delete(
    "/projects/{project_id}/templates/{template_id}",
    response_model=MessageResponse,
)
async def delete_template(
    project: ProjectDependency,
    template_id: UUID,
    session: SessionDependency,
) -> MessageResponse:
    template = await project_template(project, template_id, session)
    await ensure_no_active_references(template, session)
    template.deleted_at = utc_now()
    template.updated_at = template.deleted_at
    project.updated_at = utc_now()
    await session.commit()
    return MessageResponse(message="Template deleted")


@router.get("/templates/{template_id}/pdf")
async def template_pdf(
    template_id: UUID,
    session: SessionDependency,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    template = await session.scalar(
        select(TemplateRecord).where(
            TemplateRecord.id == template_id,
            TemplateRecord.deleted_at.is_(None),
        )
    )
    if template is None:
        raise ApiError(404, "template_not_found", "The template was not found")
    if template.project_id is not None:
        await authorized_project(template.project_id, session, authorization)
    parsed = template_from_manifest(template.manifest)
    with TemporaryDirectory(prefix="vas2font-template-") as directory:
        path = Path(directory) / download_name(template.name, template.version)
        render_template_pdf(parsed, path)
        content = path.read_bytes()
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"',
            "Cache-Control": "no-store",
        },
    )
