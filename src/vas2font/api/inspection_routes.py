from typing import Literal

from fastapi import APIRouter, Query

from vas2font.api.dependencies import ProjectDependency, SessionDependency
from vas2font.api.inspection_service import attach_previews, inspect_uploads
from vas2font.api.schemas import GlyphInspectionResponse
from vas2font.api.upload_service import active_uploads

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/glyphs", response_model=GlyphInspectionResponse)
async def inspect_glyphs(
    project: ProjectDependency,
    session: SessionDependency,
    search: str = Query(default="", max_length=100),
    status: Literal["all", "covered", "missing", "duplicates", "warnings"] = "all",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=48, ge=1, le=100),
) -> GlyphInspectionResponse:
    uploads = await active_uploads(session, project.id)
    items, counts = inspect_uploads(uploads, search, status)
    page = items[offset : offset + limit]
    attach_previews(page, uploads)
    return GlyphInspectionResponse(
        items=page,
        total=len(items),
        covered=counts["covered"],
        missing=counts["missing"],
        duplicates=counts["duplicates"],
        offset=offset,
        limit=limit,
    )
