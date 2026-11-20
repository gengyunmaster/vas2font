import math
from dataclasses import dataclass, field

from vas2font.template import PAGE_HEIGHT, PAGE_WIDTH, Rect, Template, TemplateCell
from vas2font.vas import ImageItem, Notebook, NotebookPage, Stroke, StrokePoint


@dataclass(frozen=True)
class GlyphHandwriting:
    character: str
    grid: str
    page_index: int
    writing_rect: Rect
    baseline_y: float | None
    reference_font_size: float
    strokes: tuple[Stroke, ...]


@dataclass(frozen=True)
class ExtractionResult:
    glyphs: tuple[GlyphHandwriting, ...]
    missing_characters: tuple[str, ...]
    overflow_strokes: int


@dataclass
class CellTarget:
    cell: TemplateCell
    writing_rect: Rect
    baseline_y: float | None
    reference_font_size: float
    page_index: int
    strokes: list[Stroke] = field(default_factory=list)
    has_overflow: bool = False


def transform_rect(
    rect: Rect, image: ImageItem, scale_x: float, scale_y: float
) -> Rect:
    return Rect(
        x=image.x + rect.x * scale_x,
        y=image.y + rect.y * scale_y,
        width=rect.width * scale_x,
        height=rect.height * scale_y,
    )


def build_page_targets(
    page: NotebookPage,
    page_position: int,
    template: Template,
    seen_page_indexes: set[int],
) -> list[CellTarget]:
    source = page.pdf_source
    if source is None:
        if page.strokes:
            raise ValueError(f"Page {page_position} has strokes but no PDF source")
        return []
    if source.page_index in seen_page_indexes:
        raise ValueError(f"Duplicate PDF source page: {source.page_index}")
    seen_page_indexes.add(source.page_index)
    if source.page_index >= len(template.pages):
        raise ValueError(f"Unexpected PDF source page: {source.page_index}")
    locked_images = [image for image in page.images if image.locked]
    if len(locked_images) != 1:
        raise ValueError(f"Page {page_position} must have one locked PDF image")
    image = locked_images[0]
    scale_x = image.width / PAGE_WIDTH
    scale_y = image.height / PAGE_HEIGHT
    return [
        CellTarget(
            cell=cell,
            writing_rect=transform_rect(cell.writing_rect, image, scale_x, scale_y),
            baseline_y=(
                image.y + cell.baseline_y * scale_y
                if cell.baseline_y is not None
                else None
            ),
            reference_font_size=cell.reference_font_size,
            page_index=source.page_index,
        )
        for cell in template.pages[source.page_index].cells
    ]


def stroke_center(stroke: Stroke) -> tuple[float, float]:
    xs = [point.x for point in stroke.points]
    ys = [point.y for point in stroke.points]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def contains_point(rect: Rect, point: tuple[float, float]) -> bool:
    x, y = point
    return rect.x <= x <= rect.x + rect.width and rect.y <= y <= rect.y + rect.height


def distance_to_rect(rect: Rect, point: tuple[float, float]) -> float:
    x, y = point
    dx = max(rect.x - x, 0.0, x - rect.x - rect.width)
    dy = max(rect.y - y, 0.0, y - rect.y - rect.height)
    return math.hypot(dx, dy)


def locate_target(
    targets: list[CellTarget], center: tuple[float, float]
) -> CellTarget | None:
    matches = [
        target for target in targets if contains_point(target.writing_rect, center)
    ]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return None
    ranked = sorted(
        targets, key=lambda target: distance_to_rect(target.writing_rect, center)
    )
    if not ranked:
        return None
    nearest = ranked[0]
    distance = distance_to_rect(nearest.writing_rect, center)
    tolerance = min(nearest.writing_rect.width, nearest.writing_rect.height) * 0.15
    if distance > tolerance:
        return None
    if len(ranked) > 1:
        next_distance = distance_to_rect(ranked[1].writing_rect, center)
        if next_distance - distance < 1e-6:
            return None
    return nearest


def point_outside(rect: Rect, point: StrokePoint) -> bool:
    return not contains_point(rect, (point.x, point.y))


def extract_handwriting(notebook: Notebook, template: Template) -> ExtractionResult:
    targets: list[CellTarget] = []
    seen_page_indexes: set[int] = set()
    for page_position, page in enumerate(notebook.pages):
        page_targets = build_page_targets(
            page, page_position, template, seen_page_indexes
        )
        for stroke_index, stroke in enumerate(page.strokes):
            center = stroke_center(stroke)
            target = locate_target(page_targets, center)
            if target is None:
                raise ValueError(
                    f"Cannot assign stroke {stroke_index} on notebook page {page_position} "
                    f"at {center[0]:.2f},{center[1]:.2f}"
                )
            target.strokes.append(stroke)
            if any(
                point_outside(target.writing_rect, point) for point in stroke.points
            ):
                target.has_overflow = True
        targets.extend(page_targets)
    glyphs = tuple(
        GlyphHandwriting(
            character=target.cell.character,
            grid=target.cell.grid,
            page_index=target.page_index,
            writing_rect=target.writing_rect,
            baseline_y=target.baseline_y,
            reference_font_size=target.reference_font_size,
            strokes=tuple(target.strokes),
        )
        for target in targets
        if target.strokes
    )
    covered = {glyph.character for glyph in glyphs}
    missing = tuple(
        cell.character
        for page in template.pages
        for cell in page.cells
        if cell.character not in covered
    )
    return ExtractionResult(
        glyphs=glyphs,
        missing_characters=missing,
        overflow_strokes=sum(target.has_overflow for target in targets),
    )
