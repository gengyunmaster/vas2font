from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vas2font.api.db import get_session
from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord, TemplateRecord, UploadRecord, utc_now
from vas2font.api.rate_limits import open_project_limiter
from vas2font.api.schemas import (
    MessageResponse,
    OpenProjectRequest,
    ProjectCreatedResponse,
    ProjectMetadataRequest,
    ProjectResponse,
)
from vas2font.api.security import access_code_hash, bearer_code, generate_access_code

router = APIRouter(prefix="/api")
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/projects", response_model=ProjectCreatedResponse, status_code=201)
async def create_project(
    request: ProjectMetadataRequest,
    session: SessionDependency,
) -> ProjectRecord:
    raw_code = generate_access_code()
    project = ProjectRecord(
        access_code_hash=access_code_hash(raw_code),
        font_family=request.font_family,
        font_version=request.font_version,
    )
    session.add(project)
    await session.commit()
    return ProjectCreatedResponse(
        **ProjectResponse.model_validate(project).model_dump(),
        access_code=raw_code,
    )


@router.post("/projects/open", response_model=ProjectResponse)
async def open_project(
    body: OpenProjectRequest,
    request: Request,
    session: SessionDependency,
) -> ProjectRecord:
    open_project_limiter.check(request)
    project = await session.scalar(
        select(ProjectRecord).where(
            ProjectRecord.access_code_hash == access_code_hash(body.access_code),
            ProjectRecord.deleted_at.is_(None),
        )
    )
    if project is None:
        raise ApiError(401, "invalid_access_code", "The project access code is invalid")
    return project


async def authorized_project(
    project_id: UUID,
    session: SessionDependency,
    authorization: Annotated[str | None, Header()] = None,
) -> ProjectRecord:
    project = await session.scalar(
        select(ProjectRecord).where(
            ProjectRecord.id == project_id,
            ProjectRecord.access_code_hash
            == access_code_hash(bearer_code(authorization)),
            ProjectRecord.deleted_at.is_(None),
        )
    )
    if project is None:
        raise ApiError(401, "invalid_access_code", "The project access code is invalid")
    return project


ProjectDependency = Annotated[ProjectRecord, Depends(authorized_project)]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project: ProjectDependency) -> ProjectRecord:
    return project


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def edit_project(
    body: ProjectMetadataRequest,
    project: ProjectDependency,
    session: SessionDependency,
) -> ProjectRecord:
    project.font_family = body.font_family
    project.font_version = body.font_version
    await session.commit()
    return project


@router.delete("/projects/{project_id}", response_model=MessageResponse)
async def delete_project(
    project: ProjectDependency,
    session: SessionDependency,
) -> MessageResponse:
    deleted_at = utc_now()
    await session.execute(
        update(UploadRecord)
        .where(UploadRecord.project_id == project.id, UploadRecord.deleted_at.is_(None))
        .values(deleted_at=deleted_at, updated_at=deleted_at)
    )
    await session.execute(
        update(TemplateRecord)
        .where(
            TemplateRecord.project_id == project.id, TemplateRecord.deleted_at.is_(None)
        )
        .values(deleted_at=deleted_at, updated_at=deleted_at)
    )
    project.deleted_at = deleted_at
    project.updated_at = deleted_at
    await session.commit()
    return MessageResponse(message="Project deleted")
