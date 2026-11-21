import asyncio
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from vas2font.api.config import get_settings
from vas2font.api.dependencies import ProjectDependency, SessionDependency
from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord
from vas2font.api.rate_limits import font_generation_limiter
from vas2font.api.upload_service import active_uploads, merge_upload_glyphs
from vas2font.extract import ExtractionResult
from vas2font.font import build_font

router = APIRouter(prefix="/api")
settings = get_settings()
generation_semaphore = asyncio.Semaphore(settings.generation_concurrency)


def generate_bytes(project: ProjectRecord, extraction: ExtractionResult) -> bytes:
    with TemporaryDirectory(prefix="vas2font-font-") as directory:
        path = Path(directory) / "font.otf"
        build_font(
            extraction,
            path,
            project.font_family,
            font_version=project.font_version,
        )
        return path.read_bytes()


def font_filename(family_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", family_name).strip("-")
    return f"{normalized or 'vas-handwriting'}.otf"


@router.post("/projects/{project_id}/font")
async def generate_project_font(
    request: Request,
    project: ProjectDependency,
    session: SessionDependency,
) -> Response:
    font_generation_limiter.check(request)
    uploads = await active_uploads(session, project.id)
    if not uploads:
        raise ApiError(
            409, "no_handwriting", "Upload handwriting before generating a font"
        )
    extraction = merge_upload_glyphs(uploads)
    try:
        async with generation_semaphore:
            content = await asyncio.wait_for(
                run_in_threadpool(generate_bytes, project, extraction),
                timeout=settings.generation_timeout_seconds,
            )
    except TimeoutError as error:
        raise ApiError(
            504, "generation_timeout", "Font generation exceeded the time limit"
        ) from error
    except (TypeError, ValueError, RuntimeError) as error:
        raise ApiError(
            500, "font_generation_failed", "The font could not be generated"
        ) from error
    return Response(
        content,
        media_type="application/font-sfnt",
        headers={
            "Content-Disposition": f'attachment; filename="{font_filename(project.font_family)}"',
            "Cache-Control": "no-store",
            "X-Handwritten-Glyph-Count": str(len(extraction.glyphs)),
        },
    )
