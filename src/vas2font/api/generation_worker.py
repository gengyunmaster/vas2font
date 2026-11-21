import asyncio
import os
import queue
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update

from vas2font.api.db import sessions
from vas2font.api.models import (
    GenerationJobRecord,
    ProjectRecord,
    UploadRecord,
    utc_now,
)
from vas2font.api.upload_service import merge_upload_glyphs
from vas2font.extract import ExtractionResult
from vas2font.font import build_font


def generate_font(
    family_name: str,
    font_version: str,
    extraction: ExtractionResult,
    progress_callback,
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="vas2font-build-") as directory:
        path = Path(directory) / "font.otf"
        build_font(
            extraction,
            path,
            family_name,
            font_version=font_version,
            progress_callback=progress_callback,
        )
        return path.read_bytes()


class GenerationWorker:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.results: dict[UUID, Path] = {}

    async def start(self) -> None:
        async with sessions() as session:
            await session.execute(
                update(GenerationJobRecord)
                .where(GenerationJobRecord.status.in_(["running", "succeeded"]))
                .values(
                    status="failed",
                    stage="Failed",
                    error="The generation result was interrupted or expired; generate again",
                    updated_at=utc_now(),
                    completed_at=utc_now(),
                )
            )
            await session.commit()
        self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        for path in self.results.values():
            path.unlink(missing_ok=True)
        self.results.clear()

    async def run(self) -> None:
        while True:
            job_id = await self.claim_job()
            if job_id is None:
                await asyncio.sleep(0.25)
                continue
            await self.process(job_id)

    async def claim_job(self) -> UUID | None:
        async with sessions() as session:
            job = await session.scalar(
                select(GenerationJobRecord)
                .where(
                    GenerationJobRecord.status == "queued",
                    GenerationJobRecord.deleted_at.is_(None),
                )
                .order_by(GenerationJobRecord.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            job.status = "running"
            job.stage = "Preparing handwriting"
            job.progress = 5
            job.updated_at = utc_now()
            await session.commit()
            return job.id

    async def update_progress(self, job_id: UUID, stage: str, progress: int) -> None:
        async with sessions() as session:
            await session.execute(
                update(GenerationJobRecord)
                .where(GenerationJobRecord.id == job_id)
                .values(stage=stage, progress=progress, updated_at=utc_now())
            )
            await session.commit()

    async def process(self, job_id: UUID) -> None:
        try:
            async with sessions() as session:
                job = await session.get(GenerationJobRecord, job_id)
                project = await session.get(ProjectRecord, job.project_id)
                if project.updated_at != job.input_updated_at:
                    raise ValueError(
                        "Project inputs changed before generation; generate again"
                    )
                upload_ids = [UUID(value) for value in job.upload_ids]
                uploads = list(
                    await session.scalars(
                        select(UploadRecord).where(UploadRecord.id.in_(upload_ids))
                    )
                )
                by_id = {upload.id: upload for upload in uploads}
                ordered = [by_id[upload_id] for upload_id in upload_ids]
                extraction = merge_upload_glyphs(ordered)
                family_name = job.font_family
                font_version = job.font_version
                expected_revision = job.input_updated_at
                project_id = job.project_id
            await self.update_progress(job_id, "Outlining handwriting", 15)
            events = queue.Queue()
            future = asyncio.create_task(
                asyncio.to_thread(
                    generate_font,
                    family_name,
                    font_version,
                    extraction,
                    lambda stage, progress: events.put((stage, progress)),
                )
            )
            while not future.done():
                await self.drain_progress(job_id, events)
                await asyncio.sleep(0.15)
            content = await future
            await self.drain_progress(job_id, events)
            async with sessions() as session:
                current_revision = await session.scalar(
                    select(ProjectRecord.updated_at).where(
                        ProjectRecord.id == project_id
                    )
                )
            if current_revision != expected_revision:
                raise ValueError(
                    "Project inputs changed during generation; generate again"
                )
            descriptor, filename = tempfile.mkstemp(
                prefix=f"vas2font-{job_id}-",
                suffix=".otf",
            )
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
            self.results[job_id] = Path(filename)
            async with sessions() as session:
                await session.execute(
                    update(GenerationJobRecord)
                    .where(GenerationJobRecord.id == job_id)
                    .values(
                        status="succeeded",
                        stage="Ready to download",
                        progress=100,
                        glyph_count=len(extraction.glyphs),
                        updated_at=utc_now(),
                        completed_at=utc_now(),
                    )
                )
                await session.commit()
        except Exception as error:  # noqa: BLE001 - The queue must survive individual job failures.
            async with sessions() as session:
                await session.execute(
                    update(GenerationJobRecord)
                    .where(GenerationJobRecord.id == job_id)
                    .values(
                        status="failed",
                        stage="Failed",
                        error=str(error)[:500],
                        updated_at=utc_now(),
                        completed_at=utc_now(),
                    )
                )
                await session.commit()

    async def drain_progress(self, job_id: UUID, events: queue.Queue) -> None:
        latest = None
        while not events.empty():
            latest = events.get_nowait()
        if latest is not None:
            stage, progress = latest
            await self.update_progress(job_id, stage, progress)

    def take_result(self, job_id: UUID) -> bytes | None:
        path = self.results.pop(job_id, None)
        if path is None or not path.exists():
            return None
        content = path.read_bytes()
        path.unlink()
        return content


generation_worker = GenerationWorker()
