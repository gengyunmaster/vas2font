import json
import subprocess
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path

from vas2font.vas import Stroke

Polygon = list[tuple[float, float]]


def outline_strokes(strokes: Sequence[Stroke]) -> list[Polygon]:
    if not strokes:
        return []
    script = Path(str(files("vas2font").joinpath("node/outline.mjs")))
    payload = json.dumps([stroke.outline_payload() for stroke in strokes])
    try:
        process = subprocess.run(
            ["node", str(script)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Unable to execute the stroke outline worker") from error
    if process.returncode != 0:
        raise RuntimeError(f"Stroke outline worker failed: {process.stderr.strip()}")
    raw_outlines = json.loads(process.stdout)
    if len(raw_outlines) != len(strokes):
        raise RuntimeError("Stroke outline worker returned an invalid result")
    return [
        [(float(point[0]), float(point[1])) for point in polygon]
        for polygon in raw_outlines
    ]
