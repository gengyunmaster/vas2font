import { readFileSync } from "node:fs";
import { getStroke } from "perfect-freehand";

const penOptions = { thinning: 0.75, smoothing: 0.5, streamline: 0.5 };
const highlighterOptions = { thinning: 0.35, smoothing: 0.6, streamline: 0.5 };

function boostedPressure(point) {
  if (!point.tilt) return point.pressure;
  return Math.min(1, point.pressure * (1 + point.tilt * 0.8));
}

const strokes = JSON.parse(readFileSync(0, "utf8"));
const outlines = strokes.map((stroke) => {
  const highlighter = stroke.pen === "highlighter";
  const points = highlighter
    ? stroke.points.map((point) => ({ ...point, pressure: boostedPressure(point) }))
    : stroke.points;
  return getStroke(points, {
    ...(highlighter ? highlighterOptions : penOptions),
    size: stroke.size * (highlighter ? 2.2 : 1),
    simulatePressure: stroke.simulatePressure,
    last: true,
  });
});
process.stdout.write(JSON.stringify(outlines));
