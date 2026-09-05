/** The health strip at the sizes a fresh install actually produces.
 *
 * A portal added this morning has no days yet, and one that has run once has
 * one — both are ordinary states, and both used to draw a blank cell that reads
 * as a chart that failed rather than as a portal that has not run.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DayStrip, { dayCells } from "./DayStrip";
import { en } from "../../i18n/en";
import type { ScraperHealthDay } from "../../types";

const day = (date: string, attempts: number, blocked = 0, errors = 0): ScraperHealthDay =>
  ({ date, attempts, successes: attempts - blocked - errors, blocked, errors });

describe("DayStrip", () => {
  it("says the window is empty rather than drawing nothing", () => {
    render(<DayStrip days={[]} />);
    expect(screen.getByText(en["health.noDays"])).toBeInTheDocument();
  });

  it("draws one block per day, from one day up", () => {
    for (const days of [[day("2026-03-01", 4)], [day("2026-03-01", 4), day("2026-03-02", 4)]]) {
      const { container, unmount } = render(<DayStrip days={days} />);
      expect(container.querySelectorAll("span[title]")).toHaveLength(days.length);
      unmount();
    }
  });

  it("colours a day by what actually happened on it", () => {
    const cells = dayCells([
      day("2026-03-01", 0),
      day("2026-03-02", 4),
      day("2026-03-03", 4, 1),
      day("2026-03-04", 4, 2, 2),
    ]);
    expect(cells.map((c) => c.cls)).toEqual([
      "bg-neutral-dot", "bg-positive-dot", "bg-caution-dot", "bg-negative-dot",
    ]);
    // The counts travel with the colour: "some failed" is unreadable without
    // knowing whether it was one scan in twenty or nineteen.
    expect(cells[2].label).toContain("4");
  });
});
