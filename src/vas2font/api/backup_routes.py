import json
import re

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from vas2font.api.backup_service import build_backup, import_backup
from vas2font.api.dependencies import ProjectDependency, SessionDependency
from vas2font.api.models import TemplateRecord
from vas2font.api.rate_limits import open_project_limiter
from vas2font.api.schemas import (
    ProjectCreatedResponse,
    ProjectResponse,
)
from vas2font.api.upload_service import active_uploads

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/backup")
async def download_project_backup(
    project: ProjectDependency,
    session: SessionDependency,
) -> Response:
    templates = list(
        await session.scalars(
            select(TemplateRecord).where(
                TemplateRecord.project_id == project.id,
                TemplateRecord.deleted_at.is_(None),
            )
        )
    )
    uploads = await active_uploads(session, project.id)
    backup = build_backup(project, templates, uploads)
    filename = re.sub(r"[^A-Za-z0-9_-]+", "-", project.font_family).strip("-")
    return Response(
        json.dumps(backup, ensure_ascii=False),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename or "project"}-backup.vas2font.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/projects/import", response_model=ProjectCreatedResponse, status_code=201)
async def import_project(
    data: dict,
    request: Request,
    session: SessionDependency,
) -> ProjectCreatedResponse:
    open_project_limiter.check(request)
    project, raw_code = await import_backup(data, session)
    return ProjectCreatedResponse(
        **ProjectResponse.model_validate(project).model_dump(),
        access_code=raw_code,
    )
