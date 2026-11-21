from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vas2font.api.db import get_session
from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord
from vas2font.api.security import access_code_hash, bearer_code

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


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
