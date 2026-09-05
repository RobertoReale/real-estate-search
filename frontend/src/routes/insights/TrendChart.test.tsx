/** That the chart draws something honest at every size of history.
 *
 * `chart.test.ts` covers the arithmetic; this covers what reaches the DOM,
 * which is where the three interesting cases differ. With no history there must
 * be words instead of an empty box. With one day there must be a dot and no
 * line, because two ends of a segment that is one reading long is a trend
 * invented out of nothing. With two there is a line and a fill.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TrendChart from "./TrendChart";
import { en } from "../../i18n/en";
import { expectAccessible } from "../../test/axe";
import type { PricingTrend } from "../../types";

const point = (date: string, median: number): PricingTrend["points"][number] => ({
  captured_on: date, median_sqm_price: median, sample_count: 12,
});

const ONE = [point("2026-03-01", 5000)];
const TWO = [point("2026-03-01", 5000), point("2026-03-02", 5200)];

/** Every number the SVG was actually given, attribute by attribute. */
function svgNumbers(container: HTMLElement): string[] {
  const svg = container.querySelector("svg")!;
  return [...svg.querySelectorAll("*")].flatMap((el) =>
    [...el.attributes].filter((a) => /^(c?x\d?|c?y\d?|d|r|points)$/.test(a.name))
      .map((a) => a.value));
}

describe("TrendChart", () => {
  it("says so when there is no history, instead of drawing an empty box", () => {
    const { container } = render(<TrendChart points={[]} />);
    expect(screen.getByText(en["trends.chartEmpty"])).toBeInTheDocument();
    expect(container.querySelector("svg[role='img']")).toBeNull();
  });

  it("plots a single day as a point and refuses to draw a trend through it", () => {
    const { container } = render(<TrendChart points={ONE} />);
    expect(container.querySelector("polyline")).toBeNull();
    // …but the reading itself is on the page, and labelled as one day only.
    expect(container.querySelectorAll("circle").length).toBeGreaterThan(0);
    expect(screen.getByText(en["trends.oneDayOnly"])).toBeInTheDocument();
  });

  it("draws the line and its fill from the second day", () => {
    const { container } = render(<TrendChart points={TWO} />);
    expect(container.querySelector("polyline")).toBeInTheDocument();
    expect(container.querySelector("path[fill^='url(']")).toBeInTheDocument();
    expect(screen.queryByText(en["trends.oneDayOnly"])).toBeNull();
  });

  it("emphasises the last reading whether or not there is a line", () => {
    for (const points of [ONE, TWO]) {
      const { container, unmount } = render(<TrendChart points={points} />);
      const circles = [...container.querySelectorAll("circle")];
      const last = circles[circles.length - 1];
      const halo = circles[circles.length - 2];
      expect(last.getAttribute("r")).toBe("4");
      expect(halo.getAttribute("r")).toBe("8");
      expect(last.getAttribute("cx")).toBe(halo.getAttribute("cx"));
      unmount();
    }
  });

  it("never writes NaN into an attribute", () => {
    // The failure this exists for is silent: the browser drops a coordinate it
    // cannot parse and draws the rest, so a chart with a broken scale looks
    // like a chart with no data.
    for (const points of [ONE, TWO, [point("2026-03-01", 5000), point("2026-03-01", 5000)]]) {
      const { container, unmount } = render(<TrendChart points={points} />);
      for (const value of svgNumbers(container)) {
        expect(value, `"${value}" in ${JSON.stringify(points)}`).not.toMatch(/NaN|Infinity/);
      }
      unmount();
    }
  });

  it("has no accessibility violations, empty or drawn", async () => {
    for (const points of [[], ONE, TWO]) {
      const { container, unmount } = render(<TrendChart points={points} />);
      await expectAccessible(container);
      unmount();
    }
  });
});
