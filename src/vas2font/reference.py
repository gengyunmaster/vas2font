from dataclasses import dataclass
from functools import cache, lru_cache
from importlib.resources import files
from io import BytesIO

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

REFERENCE_FONT = "TemplateReference"
FALLBACK_REFERENCE_FONT = "TemplateReferenceFallback"


@dataclass(frozen=True)
class ReferenceGlyph:
    advance: float
    bounds: tuple[float, float, float, float] | None


@lru_cache(maxsize=1)
def reference_font() -> TTFont:
    data = files("vas2font").joinpath("assets/noto-sans-sc-regular.ttf").read_bytes()
    return TTFont(BytesIO(data))


@lru_cache(maxsize=1)
def fallback_reference_font() -> TTFont:
    data = files("vas2font").joinpath("assets/noto-sans-jp-fallback.ttf").read_bytes()
    return TTFont(BytesIO(data))


@cache
def uses_fallback(character: str) -> bool:
    return ord(character) not in reference_font().getBestCmap()


def has_reference_glyph(character: str) -> bool:
    font = fallback_reference_font() if uses_fallback(character) else reference_font()
    return ord(character) in font.getBestCmap()


def pdf_reference_font_name(character: str) -> str:
    return FALLBACK_REFERENCE_FONT if uses_fallback(character) else REFERENCE_FONT


@cache
def reference_glyph(character: str, font_size: float) -> ReferenceGlyph:
    font = fallback_reference_font() if uses_fallback(character) else reference_font()
    glyph_set = font.getGlyphSet()
    name = font.getBestCmap()[ord(character)]
    scale = font_size / font["head"].unitsPerEm
    advance = font["hmtx"][name][0] * scale
    pen = BoundsPen(glyph_set)
    glyph_set[name].draw(pen)
    if pen.bounds is None:
        return ReferenceGlyph(advance=advance, bounds=None)
    x_min, y_min, x_max, y_max = pen.bounds
    return ReferenceGlyph(
        advance=advance,
        bounds=(x_min * scale, y_min * scale, x_max * scale, y_max * scale),
    )
