import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StrokePoint:
    x: float
    y: float
    pressure: float
    tilt: float | None


@dataclass(frozen=True)
class Stroke:
    pen: str
    size: float
    simulate_pressure: bool
    points: tuple[StrokePoint, ...]

    def outline_payload(self) -> dict[str, object]:
        return {
            "pen": self.pen,
            "size": self.size,
            "simulatePressure": self.simulate_pressure,
            "points": [
                {
                    "x": point.x,
                    "y": point.y,
                    "pressure": point.pressure,
                    **({"tilt": point.tilt} if point.tilt is not None else {}),
                }
                for point in self.points
            ],
        }


@dataclass(frozen=True)
class ImageItem:
    x: float
    y: float
    width: float
    height: float
    locked: bool


@dataclass(frozen=True)
class PdfSource:
    doc_id: str
    page_index: int


@dataclass(frozen=True)
class NotebookPage:
    width: float
    height: float
    strokes: tuple[Stroke, ...]
    images: tuple[ImageItem, ...]
    pdf_source: PdfSource | None


@dataclass(frozen=True)
class Notebook:
    title: str
    pages: tuple[NotebookPage, ...]


def finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Invalid {label}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Invalid {label}")
    return result


def positive_number(value: object, label: str) -> float:
    result = finite_number(value, label)
    if result <= 0:
        raise ValueError(f"Invalid {label}")
    return result


def unit_interval(value: object, label: str) -> float:
    result = finite_number(value, label)
    return min(1.0, max(0.0, result))


def parse_point(raw: object) -> StrokePoint:
    if not isinstance(raw, dict):
        raise TypeError("Invalid stroke point")
    return StrokePoint(
        x=finite_number(raw.get("x"), "point x"),
        y=finite_number(raw.get("y"), "point y"),
        pressure=unit_interval(raw.get("pressure", 0.5), "point pressure"),
        tilt=(
            unit_interval(raw["tilt"], "point tilt")
            if raw.get("tilt") is not None
            else None
        ),
    )


def parse_stroke(raw: object) -> Stroke:
    if not isinstance(raw, dict) or not isinstance(raw.get("points"), list):
        raise TypeError("Invalid stroke")
    if raw.get("shape") is not None:
        raise ValueError("Shape strokes are not supported")
    if raw.get("dash") is True:
        raise ValueError("Dashed strokes are not supported")
    pen = raw.get("pen", "pen")
    if pen not in ("pen", "highlighter"):
        raise ValueError("Unsupported pen kind")
    points = tuple(parse_point(point) for point in raw["points"])
    if not points:
        raise ValueError("Stroke has no points")
    return Stroke(
        pen=pen,
        size=positive_number(raw.get("size", 5), "stroke size"),
        simulate_pressure=raw.get("simulatePressure") is True,
        points=points,
    )


def parse_image(raw: object) -> ImageItem:
    if not isinstance(raw, dict):
        raise TypeError("Invalid image")
    return ImageItem(
        x=finite_number(raw.get("x"), "image x"),
        y=finite_number(raw.get("y"), "image y"),
        width=positive_number(raw.get("width"), "image width"),
        height=positive_number(raw.get("height"), "image height"),
        locked=raw.get("locked") is True,
    )


def parse_pdf_source(raw: object) -> PdfSource | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("docId"), str):
        raise TypeError("Invalid PDF source")
    page_index = raw.get("pageIndex")
    if isinstance(page_index, bool) or not isinstance(page_index, int):
        raise TypeError("Invalid PDF source page index")
    if page_index < 0:
        raise ValueError("Invalid PDF source page index")
    return PdfSource(doc_id=raw["docId"], page_index=page_index)


def parse_page(raw: object) -> NotebookPage:
    if not isinstance(raw, dict) or not isinstance(raw.get("strokes"), list):
        raise TypeError("Invalid notebook page")
    images = raw.get("images", [])
    if not isinstance(images, list):
        raise TypeError("Invalid page images")
    return NotebookPage(
        width=positive_number(raw.get("width", 794), "page width"),
        height=positive_number(raw.get("height", 1123), "page height"),
        strokes=tuple(parse_stroke(stroke) for stroke in raw["strokes"]),
        images=tuple(parse_image(image) for image in images),
        pdf_source=parse_pdf_source(raw.get("pdfSource")),
    )


def load_notebook(path: Path) -> Notebook:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != "vas-notebook":
        raise ValueError("Not a vas notebook file")
    version = data.get("version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not 1 <= version <= 6
    ):
        raise ValueError(f"Unsupported notebook version: {version}")
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Notebook contains no pages")
    title = data.get("title")
    return Notebook(
        title=title.strip()
        if isinstance(title, str) and title.strip()
        else "Imported notebook",
        pages=tuple(parse_page(page) for page in pages),
    )
