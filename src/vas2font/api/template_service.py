import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vas2font.api.errors import ApiError
from vas2font.api.models import TemplateRecord
from vas2font.charsets import CHARACTER_SETS, CharacterSet
from vas2font.reference import has_reference_glyph
from vas2font.template import build_template

MAX_CUSTOM_CODEPOINTS = 20_000


def normalize_characters(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFC", value)
    characters = []
    seen = set()
    unsupported = []
    for character in normalized:
        if character.isspace():
            continue
        if character in seen:
            continue
        if unicodedata.category(character).startswith("C") or not has_reference_glyph(
            character
        ):
            unsupported.append(character)
            continue
        seen.add(character)
        characters.append(character)
    if unsupported:
        raise ApiError(
            422,
            "unsupported_characters",
            "The character set contains unsupported or control characters",
            {"characters": unsupported[:50]},
        )
    if not characters:
        raise ApiError(422, "empty_character_set", "The character set is empty")
    if len(characters) > MAX_CUSTOM_CODEPOINTS:
        raise ApiError(
            422,
            "character_set_too_large",
            f"A custom template supports at most {MAX_CUSTOM_CODEPOINTS} code points",
        )
    return tuple(characters)


def custom_manifest(
    name: str,
    version: int,
    characters: tuple[str, ...],
) -> dict[str, object]:
    return build_template(CharacterSet(name, version, characters)).to_manifest()


async def ensure_builtin_templates(session: AsyncSession) -> None:
    for character_set in CHARACTER_SETS.values():
        template = await session.scalar(
            select(TemplateRecord).where(
                TemplateRecord.project_id.is_(None),
                TemplateRecord.name == character_set.identifier,
                TemplateRecord.version == character_set.version,
                TemplateRecord.deleted_at.is_(None),
            )
        )
        if template is None:
            session.add(
                TemplateRecord(
                    name=character_set.identifier,
                    version=character_set.version,
                    manifest=build_template(character_set).to_manifest(),
                )
            )
    await session.commit()


def download_name(name: str, version: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-")
    return f"{normalized or 'template'}-v{version}.pdf"
