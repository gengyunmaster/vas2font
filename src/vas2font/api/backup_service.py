import hashlib
import json
import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vas2font.api.errors import ApiError
from vas2font.api.models import ProjectRecord, TemplateRecord, UploadRecord, utc_now
from vas2font.api.schemas import ProjectMetadataRequest
from vas2font.api.security import access_code_hash, generate_access_code
from vas2font.api.upload_service import validate_notebook
from vas2font.template import template_from_manifest

BACKUP_FORMAT = "vas2font-project-backup"
BACKUP_VERSION = 1


def build_backup(
    project: ProjectRecord,
    custom_templates: Sequence[TemplateRecord],
    uploads: Sequence[UploadRecord],
) -> dict[str, object]:
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": utc_now().isoformat(),
        "project": {
            "font_family": project.font_family,
            "font_version": project.font_version,
            "pipeline_version": project.pipeline_version,
        },
        "templates": [
            {
                "name": template.name,
                "version": template.version,
                "manifest": template.manifest,
                "layout_version": template.layout_version,
                "reference_font_version": template.reference_font_version,
            }
            for template in custom_templates
        ],
        "uploads": [
            {
                "template": {
                    "built_in": upload.template.built_in,
                    "name": upload.template.name,
                    "version": upload.template.version,
                },
                "position": upload.position,
                "notebook": upload.notebook,
                "original_filename": upload.original_filename,
            }
            for upload in sorted(uploads, key=lambda item: item.position)
        ],
    }


async def import_backup(
    data: object,
    session: AsyncSession,
) -> tuple[ProjectRecord, str]:
    try:
        if not isinstance(data, dict) or data.get("format") != BACKUP_FORMAT:
            raise ValueError("Not a VAS2Font project backup")
        if data.get("version") != BACKUP_VERSION:
            raise ValueError("Unsupported project backup version")
        metadata = ProjectMetadataRequest.model_validate(data["project"])
        raw_templates = data["templates"]
        raw_uploads = data["uploads"]
        if not isinstance(raw_templates, list) or not isinstance(raw_uploads, list):
            raise TypeError("Invalid project backup contents")
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError(422, "invalid_backup", str(error)) from error
    raw_code = generate_access_code()
    project = ProjectRecord(
        access_code_hash=access_code_hash(raw_code),
        font_family=metadata.font_family,
        font_version=metadata.font_version,
        pipeline_version=str(data["project"].get("pipeline_version", "1")),
    )
    session.add(project)
    await session.flush()
    custom_templates = {}
    for raw in raw_templates:
        try:
            name = raw["name"].strip()
            version = int(raw["version"])
            manifest = raw["manifest"]
            parsed = template_from_manifest(manifest)
            if not name or parsed.character_set.identifier != name:
                raise ValueError("Template name and manifest do not match")
            if parsed.character_set.version != version:
                raise ValueError("Template version and manifest do not match")
        except (KeyError, TypeError, ValueError) as error:
            raise ApiError(422, "invalid_backup", str(error)) from error
        key = (name, version)
        if key in custom_templates:
            raise ApiError(422, "invalid_backup", "Duplicate custom template in backup")
        template = TemplateRecord(
            project_id=project.id,
            name=name,
            version=version,
            manifest=manifest,
            layout_version=str(raw.get("layout_version", "1")),
            reference_font_version=str(
                raw.get("reference_font_version", "noto-sans-sc-1")
            ),
        )
        session.add(template)
        custom_templates[key] = template
    await session.flush()
    builtin_templates = {
        (template.name, template.version): template
        for template in await session.scalars(
            select(TemplateRecord).where(
                TemplateRecord.project_id.is_(None),
                TemplateRecord.deleted_at.is_(None),
            )
        )
    }
    try:
        ordered_uploads = sorted(raw_uploads, key=lambda item: int(item["position"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError(
            422, "invalid_backup", "Invalid upload ordering in backup"
        ) from error
    for position, raw in enumerate(ordered_uploads, start=1):
        try:
            reference = raw["template"]
            key = (reference["name"], int(reference["version"]))
            template = (
                builtin_templates.get(key)
                if reference["built_in"]
                else custom_templates.get(key)
            )
            if template is None:
                raise ValueError("A referenced template is unavailable")
            notebook, extraction, report = validate_notebook(raw["notebook"], template)
            encoded = json.dumps(raw["notebook"], ensure_ascii=False).encode("utf-8")
            filename = re.split(
                r"[\\/]", str(raw.get("original_filename", "notebook.json"))
            )[-1][:255]
        except (KeyError, TypeError, ValueError) as error:
            raise ApiError(422, "invalid_backup", str(error)) from error
        session.add(
            UploadRecord(
                project_id=project.id,
                template_id=template.id,
                position=position,
                notebook=raw["notebook"],
                original_filename=filename or "notebook.json",
                file_size_bytes=len(encoded),
                sha256=hashlib.sha256(encoded).hexdigest(),
                vas_version=raw["notebook"]["version"],
                glyph_count=len(extraction.glyphs),
                stroke_count=sum(len(page.strokes) for page in notebook.pages),
                validation_report=report,
            )
        )
    project.updated_at = utc_now()
    await session.commit()
    return project, raw_code
