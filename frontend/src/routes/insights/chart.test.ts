/** The chart's arithmetic, at the three sizes that break it.
 *
 * A trend line is easy to get right with a week of data and easy to get wrong
 * with none: `Math.min(...[])` is `Infinity`, `Infinity - Infinity` is `NaN`, and
 * an SVG whose coordinates are `NaN` draws nothing and reports nothing. The same
 * hole swallows a single point (a time span of zero, divided by) and a flat run
 * (a value span of zero, divided by). Every assertion here is the same one in
 * three sizes: whatever comes in, every number that comes out is finite and
 * inside the box.
 */

import { describe, expect, it } from "vitest";
import { CHART, chartGeometry } from "./chart";
import type { PricingTrend } from "../../types";

const point = (date: string, median: number): PricingTrend["points"][number] => ({
  captured_on: date, median_sqm_price: median, sample_count: 10,
});

/** Everything the geometry hands to an attribute, flattened. */
function numbers(geom: NonNullable<ReturnType<typeof chartGeometry>>): number[] {
  return [
    ...geom.points.flatMap((p) => [p.x, p.y]),
    ...geom.grid,
    geom.yOfMin, geom.yOfMax,
    ...[geom.line, geom.area].flatMap((d) =>
      (d.match(/-?\d+(\.\d+)?/g) ?? []).map(Number)),
  ];
}

describe("chartGeometry", () => {
  it("has nothing to draw with no points", () => {
    expect(chartGeometry([])).toBeNull();
  });

  it("centres a single reading instead of pinning it to an edge", () => {
    const geom = chartGeometry([point("2026-03-01", 5000)]);
    expect(geom).not.toBeNull();
    expect(geom!.points).toHaveLength(1);
    expect(geom!.points[0].x).toBe(CHART.w / 2);
    // A lone point carries no span, so the padded scale has to put it in the
    // middle of the band rather than on the floor or through the ceiling.
    expect(geom!.points[0].y).toBeGreaterThan(CHART.padY);
    expect(geom!.points[0].y).toBeLessThan(CHART.h - CHART.padY);
  });

  it("spans the full width from the first two days", () => {
    const geom = chartGeometry([
      point("2026-03-01", 5000), point("2026-03-02", 5200),
    ])!;
    expect(geom.points[0].x).toBe(CHART.padX);
    expect(geom.points[1].x).toBe(CHART.w - CHART.padX);
    // Up in value is up on the page: y counts down from the top in SVG, so the
    // later, higher median must sit above the earlier one.
    expect(geom.points[1].y).toBeLessThan(geom.points[0].y);
    expect(geom.line.split(" ")).toHaveLength(2);
  });

  it("keeps every coordinate finite and inside the box, at every size", () => {
    const runs: PricingTrend["points"][] = [
      [point("2026-03-01", 5000)],
      [point("2026-03-01", 5000), point("2026-03-02", 5200)],
      // …a flat run, which divides by a zero value span,
      [point("2026-03-01", 5000), point("2026-03-02", 5000)],
      // …two readings on the same day, which divides by a zero time span,
      [point("2026-03-01", 5000), point("2026-03-01", 5100)],
      // …and a date the backend could not format, which parses to NaN.
      [point("not a date", 5000), point("2026-03-02", 5200)],
    ];
    for (const run of runs) {
      const geom = chartGeometry(run)!;
      for (const n of numbers(geom)) {
        expect(Number.isFinite(n), `${JSON.stringify(run)} produced ${n}`).toBe(true);
      }
      for (const p of geom.points) {
        expect(p.x).toBeGreaterThanOrEqual(CHART.padX);
        expect(p.x).toBeLessThanOrEqual(CHART.w - CHART.padX);
        expect(p.y).toBeGreaterThanOrEqual(CHART.padY);
        expect(p.y).toBeLessThanOrEqual(CHART.h - CHART.padY);
      }
    }
  });

  it("closes the area down to the baseline so the fill has a bottom", () => {
    const geom = chartGeometry([
      point("2026-03-01", 5000), point("2026-03-02", 5200),
    ])!;
    const baseline = CHART.h - CHART.padY;
    expect(geom.area.startsWith(`M ${geom.points[0].x.toFixed(1)} ${baseline}`)).toBe(true);
    expect(geom.area.endsWith(`L ${geom.points[1].x.toFixed(1)} ${baseline} Z`)).toBe(true);
  });

  it("reports the extremes and where they were plotted", () => {
    const geom = chartGeometry([
      point("2026-03-01", 4800), point("2026-03-02", 5200), point("2026-03-03", 5000),
    ])!;
    expect([geom.min, geom.max]).toEqual([4800, 5200]);
    expect(geom.yOfMin).toBe(geom.points[0].y);
    expect(geom.yOfMax).toBe(geom.points[1].y);
  });
});
