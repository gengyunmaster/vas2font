from collections.abc import Sequence

from vas2font.api.models import UploadRecord
from vas2font.api.schemas import (
    GlyphInspectionItem,
    GlyphPreview,
    GlyphPreviewPath,
)
from vas2font.extract import GlyphHandwriting, extract_handwriting, point_outside
from vas2font.template import template_from_manifest
from vas2font.vas import parse_notebook


def glyph_preview(glyph: GlyphHandwriting) -> GlyphPreview | None:
    points = [point for stroke in glyph.strokes for point in stroke.points]
    if not points:
        return None
    padding = max(3.0, max(stroke.size for stroke in glyph.strokes) * 1.5)
    min_x = min(point.x for point in points) - padding
    min_y = min(point.y for point in points) - padding
    max_x = max(point.x for point in points) + padding
    max_y = max(point.y for point in points) + padding
    paths = []
    for stroke in glyph.strokes:
        sampled = sample_stroke(stroke.points)
        first = sampled[0]
        commands = [f"M{first.x:.2f} {first.y:.2f}"]
        if len(sampled) == 1:
            commands.append("l0.01 0")
        else:
            commands.extend(f"L{point.x:.2f} {point.y:.2f}" for point in sampled[1:])
        paths.append(GlyphPreviewPath(d=" ".join(commands), stroke_width=stroke.size))
    return GlyphPreview(
        view_box=f"{min_x:.2f} {min_y:.2f} {max_x - min_x:.2f} {max_y - min_y:.2f}",
        paths=paths,
    )


def sample_stroke(points):
    if len(points) <= 60:
        return points
    return tuple(points[round(index * (len(points) - 1) / 59)] for index in range(60))


def inspect_uploads(
    uploads: Sequence[UploadRecord],
    search: str = "",
    status: str = "all",
) -> tuple[list[GlyphInspectionItem], dict[str, int]]:
    expected = {}
    contributions = {}
    for upload in sorted(uploads, key=lambda item: item.position):
        template = template_from_manifest(upload.template.manifest)
        for page in template.pages:
            for cell in page.cells:
                expected[ord(cell.character)] = cell.character
        extraction = extract_handwriting(
            parse_notebook(upload.notebook),
            template,
        )
        for glyph in extraction.glyphs:
            contributions.setdefault(ord(glyph.character), []).append((upload, glyph))
    items = []
    for codepoint, character in sorted(expected.items()):
        sources = contributions.get(codepoint, [])
        if not sources:
            items.append(
                GlyphInspectionItem(
                    character=character,
                    codepoint=codepoint,
                    status="missing",
                )
            )
            continue
        upload, glyph = sources[0]
        overflow_strokes = sum(
            any(point_outside(glyph.writing_rect, point) for point in stroke.points)
            for stroke in glyph.strokes
        )
        items.append(
            GlyphInspectionItem(
                character=character,
                codepoint=codepoint,
                status="covered",
                source_upload_id=upload.id,
                source_filename=upload.original_filename,
                source_position=upload.position,
                template_name=upload.template.name,
                template_version=upload.template.version,
                duplicate_count=len(sources),
                overridden_upload_ids=[source.id for source, _ in sources[1:]],
                overflow_strokes=overflow_strokes,
            )
        )
    counts = {
        "covered": sum(item.status == "covered" for item in items),
        "missing": sum(item.status == "missing" for item in items),
        "duplicates": sum(item.duplicate_count > 1 for item in items),
    }
    normalized_search = search.strip().upper()
    filtered = []
    for item in items:
        if normalized_search and not (
            normalized_search in item.character.upper()
            or normalized_search in f"U+{item.codepoint:04X}"
        ):
            continue
        if status == "covered" and item.status != "covered":
            continue
        if status == "missing" and item.status != "missing":
            continue
        if status == "duplicates" and item.duplicate_count < 2:
            continue
        if status == "warnings" and item.overflow_strokes == 0:
            continue
        filtered.append(item)
    return filtered, counts


def attach_previews(
    items: Sequence[GlyphInspectionItem], uploads: Sequence[UploadRecord]
) -> None:
    by_id = {upload.id: upload for upload in uploads}
    cache = {}
    for item in items:
        if item.source_upload_id is None:
            continue
        upload = by_id[item.source_upload_id]
        if upload.id not in cache:
            template = template_from_manifest(upload.template.manifest)
            extraction = extract_handwriting(parse_notebook(upload.notebook), template)
            cache[upload.id] = {glyph.character: glyph for glyph in extraction.glyphs}
        glyph = cache[upload.id].get(item.character)
        if glyph is not None:
            item.preview = glyph_preview(glyph)
