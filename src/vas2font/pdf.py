from importlib.resources import files
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from vas2font.template import (
    PAGE_HEIGHT,
    PAGE_MARGIN_X,
    PAGE_WIDTH,
    Rect,
    Template,
    TemplateCell,
)

REFERENCE_FONT = "TemplateReference"
TITLE_COLOR = HexColor("#20242A")
GUIDE_COLOR = HexColor("#AEB6C2")
INNER_GUIDE_COLOR = HexColor("#C6CCD5")


def register_reference_font() -> None:
    if REFERENCE_FONT in pdfmetrics.getRegisteredFontNames():
        return
    font_path = files("vas2font").joinpath("assets/noto-sans-sc-regular.ttf")
    with font_path.open("rb") as font_file:
        pdfmetrics.registerFont(TTFont(REFERENCE_FONT, font_file))


def pdf_y(top_y: float) -> float:
    return PAGE_HEIGHT - top_y


def rect_bottom(rect: Rect) -> float:
    return PAGE_HEIGHT - rect.y - rect.height


def draw_rice_grid(canvas: Canvas, rect: Rect) -> None:
    left = rect.x
    right = rect.x + rect.width
    bottom = rect_bottom(rect)
    top = bottom + rect.height
    center_x = rect.center_x
    center_y = bottom + rect.height / 2
    canvas.saveState()
    canvas.setStrokeColor(GUIDE_COLOR)
    canvas.setLineWidth(0.7)
    canvas.rect(left, bottom, rect.width, rect.height, stroke=1, fill=0)
    canvas.setStrokeColor(INNER_GUIDE_COLOR)
    canvas.setLineWidth(0.45)
    canvas.setDash(2, 2)
    canvas.line(left, center_y, right, center_y)
    canvas.line(center_x, bottom, center_x, top)
    canvas.line(left, bottom, right, top)
    canvas.line(left, top, right, bottom)
    canvas.restoreState()


def draw_four_line_grid(canvas: Canvas, cell: TemplateCell) -> None:
    if cell.baseline_y is None or cell.x_height_y is None:
        raise ValueError("Four-line grid requires x-height and baseline guides")
    rect = cell.writing_rect
    canvas.saveState()
    canvas.setStrokeColor(GUIDE_COLOR)
    canvas.setLineWidth(0.7)
    canvas.setDash()
    canvas.rect(
        rect.x,
        rect_bottom(rect),
        rect.width,
        rect.height,
        stroke=1,
        fill=0,
    )
    canvas.setStrokeColor(INNER_GUIDE_COLOR)
    canvas.setLineWidth(0.45)
    canvas.setDash(2, 2)
    right = rect.x + rect.width
    canvas.line(rect.x, pdf_y(cell.x_height_y), right, pdf_y(cell.x_height_y))
    canvas.line(rect.x, pdf_y(cell.baseline_y), right, pdf_y(cell.baseline_y))
    canvas.restoreState()


def draw_reference_character(canvas: Canvas, cell: TemplateCell) -> None:
    canvas.saveState()
    canvas.setFillColor(TITLE_COLOR)
    canvas.setFont(REFERENCE_FONT, cell.reference_font_size)
    if cell.baseline_y is not None:
        baseline = pdf_y(cell.baseline_y)
    else:
        ascent, descent = pdfmetrics.getAscentDescent(
            REFERENCE_FONT, cell.reference_font_size
        )
        center_y = rect_bottom(cell.reference_rect) + cell.reference_rect.height / 2
        baseline = center_y - (ascent + descent) / 2
    canvas.drawCentredString(cell.reference_rect.center_x, baseline, cell.character)
    canvas.restoreState()


def draw_header(canvas: Canvas, template: Template, page_index: int) -> None:
    canvas.setFillColor(TITLE_COLOR)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(PAGE_MARGIN_X, pdf_y(30), "VAS2Font Handwriting Template")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        PAGE_MARGIN_X,
        pdf_y(48),
        f"Charset: {template.character_set.identifier} | Version: {template.character_set.version}",
    )
    canvas.drawRightString(
        PAGE_WIDTH - PAGE_MARGIN_X,
        pdf_y(48),
        f"Page {page_index + 1} of {len(template.pages)}",
    )
    canvas.setStrokeColor(GUIDE_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(PAGE_MARGIN_X, pdf_y(60), PAGE_WIDTH - PAGE_MARGIN_X, pdf_y(60))


def draw_footer(canvas: Canvas) -> None:
    canvas.setFillColor(TITLE_COLOR)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(
        PAGE_WIDTH / 2,
        30,
        "Write only in the right-hand grid and keep each character within its assigned cell.",
    )


def render_template_pdf(template: Template, path: Path) -> None:
    register_reference_font()
    canvas = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT), pageCompression=1)
    canvas.setTitle(
        f"VAS2Font {template.character_set.identifier} v{template.character_set.version}"
    )
    canvas.setAuthor("VAS2Font")
    canvas.setSubject("Handwriting template")
    for page in template.pages:
        draw_header(canvas, template, page.page_index)
        for cell in page.cells:
            draw_reference_character(canvas, cell)
            if cell.grid == "rice":
                draw_rice_grid(canvas, cell.writing_rect)
            else:
                draw_four_line_grid(canvas, cell)
        draw_footer(canvas)
        canvas.showPage()
    canvas.save()
