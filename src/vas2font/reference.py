from dataclasses import dataclass
from functools import cache, lru_cache
from importlib.resources import files
from io import BytesIO

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont


@dataclass(frozen=True)
class ReferenceGlyph:
    advance: float
    bounds: tuple[float, float, float, float] | None


@lru_cache(maxsize=1)
def reference_font() -> TTFont:
    data = files("vas2font").joinpath("assets/noto-sans-sc-regular.ttf").read_bytes()
    return TTFont(BytesIO(data))


@cache
def reference_glyph(character: str, font_size: float) -> ReferenceGlyph:
    font = reference_font()
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
