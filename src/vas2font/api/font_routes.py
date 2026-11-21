import re
from uuid import UUID

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from vas2font.api.dependencies import ProjectDependency, SessionDependency
from vas2font.api.errors import ApiError
from vas2font.api.generation_worker import generation_worker
from vas2font.api.models import GenerationJobRecord, utc_now
from vas2font.api.rate_limits import font_generation_limiter
from vas2font.api.schemas import GenerationJobResponse
from vas2font.api.upload_service import active_uploads

router = APIRouter(prefix="/api")


def font_filename(family_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", family_name).strip("-")
    return f"{normalized or 'vas-handwriting'}.otf"


@router.post(
    "/projects/{project_id}/font",
    response_model=GenerationJobResponse,
    status_code=202,
)
async def enqueue_font_generation(
    request: Request,
    project: ProjectDependency,
    session: SessionDependency,
) -> GenerationJobRecord:
    font_generation_limiter.check(request)
    existing = await session.scalar(
        select(GenerationJobRecord)
        .where(
            GenerationJobRecord.project_id == project.id,
            GenerationJobRecord.status.in_(["queued", "running"]),
            GenerationJobRecord.deleted_at.is_(None),
        )
        .order_by(GenerationJobRecord.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    uploads = await active_uploads(session, project.id)
    if not uploads:
        raise ApiError(
            409, "no_handwriting", "Upload handwriting before generating a font"
        )
    job = GenerationJobRecord(
        project_id=project.id,
        font_family=project.font_family,
        font_version=project.font_version,
        upload_ids=[str(upload.id) for upload in uploads],
        input_updated_at=project.updated_at,
    )
    session.add(job)
    await session.commit()
    return job


async def generation_job(
    project_id: UUID,
    job_id: UUID,
    session: SessionDependency,
) -> GenerationJobRecord:
    job = await session.scalar(
        select(GenerationJobRecord).where(
            GenerationJobRecord.id == job_id,
            GenerationJobRecord.project_id == project_id,
            GenerationJobRecord.deleted_at.is_(None),
        )
    )
    if job is None:
        raise ApiError(
            404, "generation_job_not_found", "The generation job was not found"
        )
    return job


@router.get(
    "/projects/{project_id}/font/jobs/{job_id}",
    response_model=GenerationJobResponse,
)
async def get_generation_job(
    project: ProjectDependency,
    job_id: UUID,
    session: SessionDependency,
) -> GenerationJobRecord:
    return await generation_job(project.id, job_id, session)


@router.get("/projects/{project_id}/font/jobs/{job_id}/download")
async def download_generation_result(
    project: ProjectDependency,
    job_id: UUID,
    session: SessionDependency,
) -> Response:
    job = await generation_job(project.id, job_id, session)
    if job.status != "succeeded":
        raise ApiError(
            409, "generation_not_ready", "The font is not ready for download"
        )
    content = generation_worker.take_result(job.id)
    if content is None:
        raise ApiError(
            410,
            "generation_result_unavailable",
            "The generated font has expired; generate it again",
        )
    job.downloaded_at = utc_now()
    job.updated_at = job.downloaded_at
    await session.commit()
    return Response(
        content,
        media_type="application/font-sfnt",
        headers={
            "Content-Disposition": f'attachment; filename="{font_filename(project.font_family)}"',
            "Cache-Control": "no-store",
            "X-Handwritten-Glyph-Count": str(job.glyph_count),
        },
    )
