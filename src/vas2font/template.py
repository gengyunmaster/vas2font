import json
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4

from vas2font.charsets import CharacterSet
from vas2font.reference import reference_glyph

PAGE_WIDTH, PAGE_HEIGHT = A4
PAGE_MARGIN_X = 28.0
CONTENT_TOP = 72.0
COLUMN_COUNT = 5
ROW_COUNT = 11
CHARACTERS_PER_PAGE = 52
ROW_HEIGHT = 64.0
GRID_SIZE = 48.0
GRID_GAP = 8.0
REFERENCE_FONT_SIZE = GRID_SIZE
LATIN_REFERENCE_FONT_SIZE = 40.0
LATIN_WIDTHS = (24.0, 32.0, 40.0)
LATIN_EDGE_MARGIN = 2.5
LATIN_WIDTH_PADDING = 2.0


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    def to_dict(self) -> dict[str, float]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
        }


@dataclass(frozen=True)
class TemplateCell:
    character: str
    row: int
    column: int
    grid: str
    reference_rect: Rect
    writing_rect: Rect
    reference_font_size: float
    baseline_y: float | None
    x_height_y: float | None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "character": self.character,
            "codepoint": ord(self.character),
            "row": self.row,
            "column": self.column,
            "grid": self.grid,
            "reference_rect": self.reference_rect.to_dict(),
            "writing_rect": self.writing_rect.to_dict(),
            "reference_font_size": self.reference_font_size,
        }
        if self.baseline_y is not None:
            result["baseline_y"] = round(self.baseline_y, 4)
        if self.x_height_y is not None:
            result["x_height_y"] = round(self.x_height_y, 4)
        return result


@dataclass(frozen=True)
class TemplatePage:
    page_index: int
    cells: tuple[TemplateCell, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "cells": [cell.to_dict() for cell in self.cells],
        }


@dataclass(frozen=True)
class Template:
    character_set: CharacterSet
    pages: tuple[TemplatePage, ...]

    def to_manifest(self) -> dict[str, object]:
        return {
            "format": "vas2font-template",
            "format_version": 1,
            "charset_id": self.character_set.identifier,
            "charset_version": self.character_set.version,
            "character_count": len(self.character_set.characters),
            "reference_font_size": {"value": REFERENCE_FONT_SIZE, "unit": "pt"},
            "coordinate_system": "top-left",
            "page_size": {
                "width": round(PAGE_WIDTH, 4),
                "height": round(PAGE_HEIGHT, 4),
                "unit": "pt",
            },
            "pages": [page.to_dict() for page in self.pages],
        }


def grid_for_character(character: str) -> str:
    return "rice" if "\u4e00" <= character <= "\u9fff" else "four-line"


def latin_guides(characters: tuple[str, ...]) -> tuple[float, float]:
    glyphs = [
        reference_glyph(character, LATIN_REFERENCE_FONT_SIZE)
        for character in characters
    ]
    outlines = [glyph.bounds for glyph in glyphs if glyph.bounds is not None]
    highest = max(bounds[3] for bounds in outlines)
    lowest = max(-bounds[1] for bounds in outlines)
    baseline_offset = LATIN_EDGE_MARGIN + highest
    if baseline_offset + lowest + LATIN_EDGE_MARGIN > GRID_SIZE + 1e-6:
        raise ValueError("Latin reference characters exceed the writing cell")
    x_bounds = reference_glyph("x", LATIN_REFERENCE_FONT_SIZE).bounds
    if x_bounds is None:
        raise ValueError("Reference font has no x-height glyph")
    return baseline_offset, baseline_offset - x_bounds[3]


def latin_width(character: str) -> float:
    glyph = reference_glyph(character, LATIN_REFERENCE_FONT_SIZE)
    overhang = 0.0
    if glyph.bounds is not None:
        x_min, _, x_max, _ = glyph.bounds
        overhang = max(0.0, -x_min, x_max - glyph.advance)
    required_width = glyph.advance + overhang * 2 + LATIN_WIDTH_PADDING
    for width in LATIN_WIDTHS:
        if required_width <= width + 1e-6:
            return width
    raise ValueError(f"Reference character is too wide: {character}")


def build_cell(
    character: str,
    row: int,
    column: int,
    box_width: float,
    font_size: float,
    baseline_offset: float | None,
    x_height_offset: float | None,
) -> TemplateCell:
    column_width = (PAGE_WIDTH - PAGE_MARGIN_X * 2) / COLUMN_COUNT
    pair_width = box_width * 2 + GRID_GAP
    pair_x = PAGE_MARGIN_X + column * column_width + (column_width - pair_width) / 2
    grid_y = CONTENT_TOP + row * ROW_HEIGHT + (ROW_HEIGHT - GRID_SIZE) / 2
    return TemplateCell(
        character=character,
        row=row,
        column=column,
        grid=grid_for_character(character),
        reference_rect=Rect(pair_x, grid_y, box_width, GRID_SIZE),
        writing_rect=Rect(pair_x + box_width + GRID_GAP, grid_y, box_width, GRID_SIZE),
        reference_font_size=font_size,
        baseline_y=(grid_y + baseline_offset if baseline_offset is not None else None),
        x_height_y=(grid_y + x_height_offset if x_height_offset is not None else None),
    )


def build_template(character_set: CharacterSet) -> Template:
    latin_characters = tuple(
        character
        for character in character_set.characters
        if grid_for_character(character) == "four-line"
    )
    baseline_offset, x_height_offset = latin_guides(latin_characters)
    pages = []
    for page_index, offset in enumerate(
        range(0, len(character_set.characters), CHARACTERS_PER_PAGE)
    ):
        characters = character_set.characters[offset : offset + CHARACTERS_PER_PAGE]
        if len(characters) > ROW_COUNT * COLUMN_COUNT:
            raise ValueError("Template page capacity exceeded")
        cells = []
        for index, character in enumerate(characters):
            is_latin = grid_for_character(character) == "four-line"
            cells.append(
                build_cell(
                    character=character,
                    row=index // COLUMN_COUNT,
                    column=index % COLUMN_COUNT,
                    box_width=(latin_width(character) if is_latin else GRID_SIZE),
                    font_size=(
                        LATIN_REFERENCE_FONT_SIZE if is_latin else REFERENCE_FONT_SIZE
                    ),
                    baseline_offset=baseline_offset if is_latin else None,
                    x_height_offset=x_height_offset if is_latin else None,
                )
            )
        pages.append(TemplatePage(page_index=page_index, cells=tuple(cells)))
    return Template(character_set=character_set, pages=tuple(pages))


def write_manifest(template: Template, path: Path) -> None:
    path.write_text(
        json.dumps(template.to_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
