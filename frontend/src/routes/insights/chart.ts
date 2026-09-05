/** Where a trend line goes, separated from what it looks like.
 *
 *  It is here rather than inside the component because the interesting part of a
 *  chart is arithmetic, and arithmetic can be asserted without a DOM. The three
 *  cases that matter are the small ones: no history, one day of history, and the
 *  two days that first make a line. The old version derived its scale from
 *  `Math.min(...xs)`, which is `Infinity` on an empty array and `NaN` once it
 *  reaches a coordinate — an SVG full of `NaN` renders as nothing at all, with no
 *  error anywhere to say so. Every number this returns is finite for every input,
 *  and that is the property the tests hold it to.
 */
import type { PricingTrend } from "../../types";

/** The user-space box every path below is expressed in. Wide and shallow: the
 *  SVG scales to its container, so the aspect ratio here is the shape the chart
 *  has on the page. */
export const CHART = { w: 600, h: 140, padX: 10, padY: 16 } as const;

/** How many horizontal rules the faint grid is drawn with, top and bottom
 *  included. */
const GRID_LINES = 5;

export interface ChartPoint {
  x: number;
  y: number;
  /** The median this point was plotted from, for the label and the tooltip. */
  value: number;
  /** `captured_on`, which is also the React key: one snapshot per area per day. */
  date: string;
}

export interface ChartGeometry {
  points: ChartPoint[];
  /** The run of points, ready for a `<polyline points=…>`. */
  line: string;
  /** The same run closed down to the baseline, ready for a `<path d=…>`. */
  area: string;
  /** The y of each grid rule. */
  grid: number[];
  /** The extremes, and where they sit — the axis labels are HTML, positioned
   *  against these rather than guessed at. */
  min: number;
  max: number;
  yOfMin: number;
  yOfMax: number;
}

/** `null` when there is nothing to draw. Anything else is drawable. */
export function chartGeometry(points: PricingTrend["points"]): ChartGeometry | null {
  const n = points.length;
  if (n === 0) return null;

  const { w, h, padX, padY } = CHART;
  const left = padX;
  const right = w - padX;
  const top = padY;
  const bottom = h - padY;

  // The x scale is time when time says something, and the index when it does
  // not: one point spans no time at all, and a date the backend could not format
  // parses to NaN. Both fall through to an even spread, which is the honest
  // reading of "these are consecutive daily snapshots" anyway.
  const times = points.map((p) => new Date(p.captured_on).getTime());
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const byTime = times.every(Number.isFinite) && maxT > minT;
  const px = (i: number) =>
    byTime
      ? left + ((times[i] - minT) / (maxT - minT)) * (right - left)
      : n === 1
        ? (left + right) / 2
        : left + (i / (n - 1)) * (right - left);

  // The y scale never collapses: a flat week of medians would otherwise divide
  // by zero and put every point on the same edge of the box.
  const values = points.map((p) => p.median_sqm_price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.08 || Math.abs(max) * 0.08 || 1;
  const lo = min - pad;
  const span = max + pad - lo;
  const py = (v: number) => bottom - ((v - lo) / span) * (bottom - top);

  const plotted: ChartPoint[] = points.map((p, i) => ({
    x: px(i), y: py(p.median_sqm_price), value: p.median_sqm_price,
    date: p.captured_on,
  }));

  const xy = (p: ChartPoint) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  const first = plotted[0];
  const last = plotted[n - 1];

  return {
    points: plotted,
    line: plotted.map(xy).join(" "),
    area: [
      `M ${first.x.toFixed(1)} ${bottom}`,
      ...plotted.map((p) => `L ${xy(p).replace(",", " ")}`),
      `L ${last.x.toFixed(1)} ${bottom}`,
      "Z",
    ].join(" "),
    grid: Array.from(
      { length: GRID_LINES },
      (_, i) => top + (i / (GRID_LINES - 1)) * (bottom - top),
    ),
    min, max, yOfMin: py(min), yOfMax: py(max),
  };
}
