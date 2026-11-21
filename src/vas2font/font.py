import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.psCharStrings import T2CharString
from fontTools.misc.timeTools import timestampNow
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from reportlab.pdfbase import pdfmetrics

from vas2font.extract import ExtractionResult, GlyphHandwriting
from vas2font.outline import Polygon, outline_strokes
from vas2font.pdf import REFERENCE_FONT, register_reference_font
from vas2font.reference import pdf_reference_font_name, reference_glyph
from vas2font.template import GRID_SIZE

UNITS_PER_EM = 1000
MIN_SIDE_BEARING = 30
CJK_SIDE_BEARING = 20
MIN_GLYPH_SCALE = 0.8
MAX_GLYPH_SCALE = 1.4
REGULAR_STYLE = 1 << 6
LATIN_1_CODE_PAGE = 1 << 0
SIMPLIFIED_CHINESE_CODE_PAGE = 1 << 18

Bounds = tuple[float, float, float, float]


@dataclass(frozen=True)
class FontBuildResult:
    path: Path
    glyph_count: int
    mapped_character_count: int
    outline_point_count: int
    ttf_path: Path | None = None


@dataclass(frozen=True)
class GlyphTransform:
    advance_width: int
    transform: Callable[[tuple[float, float]], tuple[float, float]]


@dataclass(frozen=True)
class CompiledGlyph:
    char_string: T2CharString
    bounds: Bounds | None
    advance_width: int
    point_count: int


@dataclass(frozen=True)
class GlyphNormalization:
    scale: float
    translate_x: float
    translate_y: float
    bounds: Bounds | None


def glyph_name(character: str) -> str:
    codepoint = ord(character)
    return f"uni{codepoint:04X}" if codepoint <= 0xFFFF else f"u{codepoint:05X}"


def glyph_transform(glyph: GlyphHandwriting) -> GlyphTransform:
    register_reference_font()
    rect = glyph.writing_rect
    font_size = glyph.reference_font_size
    scale = rect.height / GRID_SIZE
    advance_points = pdfmetrics.stringWidth(
        glyph.character, pdf_reference_font_name(glyph.character), font_size
    )
    advance_width = round(advance_points * UNITS_PER_EM / font_size)
    advance_vas = advance_points * scale
    origin_x = rect.x + (rect.width - advance_vas) / 2
    if glyph.baseline_y is not None:
        baseline_y = glyph.baseline_y
    else:
        ascent, descent = pdfmetrics.getAscentDescent(REFERENCE_FONT, font_size)
        baseline_from_bottom = GRID_SIZE / 2 - (ascent + descent) / 2
        baseline_y = rect.y + rect.height - baseline_from_bottom * scale
    units_per_vas_unit = UNITS_PER_EM / (font_size * scale)

    def transform(point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return (
            (x - origin_x) * units_per_vas_unit,
            (baseline_y - y) * units_per_vas_unit,
        )

    return GlyphTransform(advance_width=advance_width, transform=transform)


def simplified_path(
    outlines: list[Polygon],
    transform: Callable[[tuple[float, float]], tuple[float, float]],
) -> pathops.Path:
    path = pathops.Path()
    pen = path.getPen()
    for outline in outlines:
        if not outline:
            continue
        first, *remaining = outline
        pen.moveTo(transform(first))
        for point in remaining:
            pen.lineTo(transform(point))
        pen.closePath()
    return pathops.simplify(path)


def normalize_glyph(
    glyph: GlyphHandwriting,
    bounds: Bounds | None,
) -> GlyphNormalization:
    reference = reference_glyph(glyph.character, glyph.reference_font_size)
    if bounds is None or reference.bounds is None:
        return GlyphNormalization(1.0, 0.0, 0.0, bounds)
    reference_units = UNITS_PER_EM / glyph.reference_font_size
    reference_bounds = tuple(value * reference_units for value in reference.bounds)
    x_min, y_min, x_max, y_max = bounds
    ref_x_min, ref_y_min, ref_x_max, ref_y_max = reference_bounds
    handwriting_width = x_max - x_min
    handwriting_height = y_max - y_min
    reference_width = ref_x_max - ref_x_min
    reference_height = ref_y_max - ref_y_min
    if (
        glyph.grid == "four-line"
        and glyph.character.isalnum()
        and handwriting_height > 1e-6
        and reference_height > 1e-6
    ):
        scale = reference_height / handwriting_height
    else:
        handwriting_size = math.hypot(handwriting_width, handwriting_height)
        reference_size = math.hypot(reference_width, reference_height)
        if handwriting_size <= 1e-6 or reference_size <= 1e-6:
            return GlyphNormalization(1.0, 0.0, 0.0, bounds)
        scale = reference_size / handwriting_size
    scale = min(MAX_GLYPH_SCALE, max(MIN_GLYPH_SCALE, scale))
    if glyph.grid == "rice" and handwriting_width > 1e-6:
        reference_advance = reference.advance * reference_units
        available_width = reference_advance - CJK_SIDE_BEARING * 2
        scale = min(scale, available_width / handwriting_width)
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    reference_center_x = (ref_x_min + ref_x_max) / 2
    reference_center_y = (ref_y_min + ref_y_max) / 2
    translate_x = reference_center_x - center_x * scale
    translate_y = reference_center_y - center_y * scale
    normalized_bounds = (
        x_min * scale + translate_x,
        y_min * scale + translate_y,
        x_max * scale + translate_x,
        y_max * scale + translate_y,
    )
    return GlyphNormalization(scale, translate_x, translate_y, normalized_bounds)


def fit_glyph_metrics(
    bounds: Bounds | None,
    reference_advance: int,
    grid: str,
) -> tuple[float, int, Bounds | None]:
    if bounds is None:
        return 0.0, reference_advance, None
    x_min, y_min, x_max, y_max = bounds
    side_bearing = CJK_SIDE_BEARING if grid == "rice" else MIN_SIDE_BEARING
    x_offset = max(0.0, side_bearing - x_min)
    required_advance = math.ceil(x_max + x_offset + side_bearing)
    advance_width = max(reference_advance, required_advance)
    ink_width = x_max - x_min
    if (
        grid == "rice"
        and advance_width > reference_advance
        and ink_width + side_bearing * 2 <= reference_advance + 1e-6
    ):
        x_offset = (reference_advance - ink_width) / 2 - x_min
        advance_width = reference_advance
    adjusted_bounds = (x_min + x_offset, y_min, x_max + x_offset, y_max)
    return x_offset, advance_width, adjusted_bounds


def glyph_char_string(
    outlines: list[Polygon],
    glyph: GlyphHandwriting,
) -> CompiledGlyph:
    glyph_transform_data = glyph_transform(glyph)
    path = simplified_path(outlines, glyph_transform_data.transform)
    bounds_pen = BoundsPen(None)
    path.draw(bounds_pen)
    normalization = normalize_glyph(glyph, bounds_pen.bounds)
    x_offset, advance_width, bounds = fit_glyph_metrics(
        normalization.bounds, glyph_transform_data.advance_width, glyph.grid
    )
    pen = T2CharStringPen(advance_width, None)
    transform = Transform(
        normalization.scale,
        0,
        0,
        normalization.scale,
        normalization.translate_x + x_offset,
        normalization.translate_y,
    )
    path.draw(TransformPen(pen, transform))
    return CompiledGlyph(
        char_string=pen.getCharString(),
        bounds=bounds,
        advance_width=advance_width,
        point_count=sum(len(outline) for outline in outlines),
    )


def notdef_char_string() -> T2CharString:
    pen = T2CharStringPen(600, None)
    pen.moveTo((80, 0))
    pen.lineTo((520, 0))
    pen.lineTo((520, 700))
    pen.lineTo((80, 700))
    pen.closePath()
    pen.moveTo((140, 60))
    pen.lineTo((140, 640))
    pen.lineTo((460, 640))
    pen.lineTo((460, 60))
    pen.closePath()
    return pen.getCharString()


def postscript_name(family_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", family_name)
    return f"{normalized or 'VASHandwriting'}-Regular"


def font_names(family_name: str, font_version: str = "0.1") -> dict[str, str]:
    return {
        "familyName": family_name,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{family_name} Regular {font_version}",
        "fullName": f"{family_name} Regular",
        "psName": postscript_name(family_name),
        "version": f"Version {font_version}",
    }


def build_ttf_companion(
    source_path: Path,
    output_path: Path,
    family_name: str,
    font_version: str,
) -> None:
    with TTFont(source_path) as source:
        glyph_set = source.getGlyphSet()
        glyph_order = source.getGlyphOrder()
        character_map = source.getBestCmap()
        glyphs = {}
        for name in glyph_order:
            pen = TTGlyphPen(glyph_set)
            glyph_set[name].draw(Cu2QuPen(pen, max_err=1.0))
            glyphs[name] = pen.glyph()
        builder = FontBuilder(source["head"].unitsPerEm, isTTF=True)
        builder.setupHead(
            fontRevision=source["head"].fontRevision,
            created=source["head"].created,
            modified=timestampNow(),
        )
        builder.setupGlyphOrder(glyph_order)
        builder.setupCharacterMap(character_map)
        builder.setupGlyf(glyphs)
        metrics = {
            name: (
                source["hmtx"][name][0],
                glyph.xMin if glyph.numberOfContours else 0,
            )
            for name, glyph in glyphs.items()
        }
        builder.setupHorizontalMetrics(metrics)
        builder.setupHorizontalHeader(
            ascent=source["hhea"].ascent,
            descent=source["hhea"].descent,
        )
        builder.setupNameTable(font_names(family_name, font_version), mac=False)
        builder.setupOS2(
            sTypoAscender=source["OS/2"].sTypoAscender,
            sTypoDescender=source["OS/2"].sTypoDescender,
            usWinAscent=source["OS/2"].usWinAscent,
            usWinDescent=source["OS/2"].usWinDescent,
            ulCodePageRange1=source["OS/2"].ulCodePageRange1,
            ulCodePageRange2=source["OS/2"].ulCodePageRange2,
            fsType=0,
            fsSelection=REGULAR_STYLE,
            achVendID="VAS2",
        )
        builder.setupPost(
            underlinePosition=source["post"].underlinePosition,
            underlineThickness=source["post"].underlineThickness,
        )
        builder.setupDummyDSIG()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        builder.save(output_path)
    with TTFont(output_path) as font:
        if (
            font.sfntVersion != "\x00\x01\x00\x00"
            or font.getBestCmap() != character_map
        ):
            raise RuntimeError("Generated TrueType font validation failed")


def build_font(
    extraction: ExtractionResult,
    output_path: Path,
    family_name: str,
    ttf_output_path: Path | None = None,
    font_version: str = "0.1",
) -> FontBuildResult:
    if not extraction.glyphs:
        raise ValueError("No handwriting was found")
    strokes = [stroke for glyph in extraction.glyphs for stroke in glyph.strokes]
    outlines = outline_strokes(strokes)
    outline_offset = 0
    char_strings = {".notdef": notdef_char_string()}
    metrics = {".notdef": (600, 80)}
    glyph_bounds: dict[str, Bounds | None] = {".notdef": (80.0, 0.0, 520.0, 700.0)}
    outline_point_count = 0
    for glyph in extraction.glyphs:
        glyph_outlines = outlines[outline_offset : outline_offset + len(glyph.strokes)]
        outline_offset += len(glyph.strokes)
        compiled = glyph_char_string(glyph_outlines, glyph)
        name = glyph_name(glyph.character)
        char_strings[name] = compiled.char_string
        glyph_bounds[name] = compiled.bounds
        metrics[name] = (
            compiled.advance_width,
            round(compiled.bounds[0]) if compiled.bounds else 0,
        )
        outline_point_count += compiled.point_count
    space_width = round(reference_glyph(" ", 1.0).advance * UNITS_PER_EM)
    for name in ("space", "nbsp"):
        char_strings[name] = T2CharStringPen(space_width, None).getCharString()
        metrics[name] = (space_width, 0)
        glyph_bounds[name] = None
    glyph_order = [
        ".notdef",
        "space",
        "nbsp",
        *(glyph_name(glyph.character) for glyph in extraction.glyphs),
    ]
    character_map = {
        0x20: "space",
        0xA0: "nbsp",
        **{
            ord(glyph.character): glyph_name(glyph.character)
            for glyph in extraction.glyphs
        },
    }
    builder = FontBuilder(UNITS_PER_EM, isTTF=False)
    builder.setupHead(
        fontRevision=float(font_version),
        created=timestampNow(),
        modified=timestampNow(),
    )
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(character_map)
    names = font_names(family_name, font_version)
    ps_name = names["psName"]
    builder.setupCFF(
        ps_name,
        {
            "FullName": names["fullName"],
            "FamilyName": family_name,
            "Weight": "Regular",
        },
        char_strings,
        {},
    )
    valid_bounds = [bound for bound in glyph_bounds.values() if bound is not None]
    y_max = max(bound[3] for bound in valid_bounds)
    y_min = min(bound[1] for bound in valid_bounds)
    ascent = max(1000, math.ceil(y_max + 50))
    descent = min(-300, math.floor(y_min - 50))
    code_page_range = 0
    if any(codepoint <= 0x00FF for codepoint in character_map):
        code_page_range |= LATIN_1_CODE_PAGE
    if any(0x4E00 <= codepoint <= 0x9FFF for codepoint in character_map):
        code_page_range |= SIMPLIFIED_CHINESE_CODE_PAGE
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=ascent, descent=descent)
    builder.setupNameTable(names, mac=False)
    builder.setupOS2(
        sTypoAscender=ascent,
        sTypoDescender=descent,
        usWinAscent=ascent,
        usWinDescent=-descent,
        ulCodePageRange1=code_page_range,
        fsType=0,
        fsSelection=REGULAR_STYLE,
        achVendID="VAS2",
    )
    builder.setupPost(underlinePosition=-100, underlineThickness=50)
    builder.setupDummyDSIG()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(output_path)
    with TTFont(output_path) as font:
        if font.sfntVersion != "OTTO" or font.getBestCmap() != character_map:
            raise RuntimeError("Generated font validation failed")
    if ttf_output_path is not None:
        build_ttf_companion(
            output_path,
            ttf_output_path,
            f"{family_name} TT",
            font_version,
        )
    return FontBuildResult(
        path=output_path,
        glyph_count=len(glyph_order),
        mapped_character_count=len(character_map),
        outline_point_count=outline_point_count,
        ttf_path=ttf_output_path,
    )
