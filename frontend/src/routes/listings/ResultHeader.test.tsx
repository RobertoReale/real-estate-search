/** The header over the results says what is on screen and how it is arranged,
 *  and nothing else. Two things are worth holding still.
 *
 *  The first is naming: the sort is a `<select>` and needs a label associated
 *  with it, and the view switch is a pair of buttons with no control to label,
 *  so it carries `role="group"` instead. Both were true of the filter bar this
 *  came out of and both are easy to lose in a move.
 *
 *  The second is the "best match" sort, which ranks by a score the backend only
 *  computes when the user has configured a dream home. Left selected with the
 *  feature off, the backend silently returns the grid unsorted — so the header
 *  is what puts the sort back to something that means anything.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ResultHeader from "./ResultHeader";
import { en } from "../../i18n/en";
import type { PropertyFilters } from "../../types";

const FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "", zone: "", q: "", source: "",
  profile_id: "", tag: "", min_price: "", max_price: "", min_sqm: "",
  max_sqm: "", floor_band: "", rooms: "",
  portal: "", agency: "", deal: "", min_sqm_price: "", max_sqm_price: "",
  merged_only: false,
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: false, sort: "newest",
};

describe("ResultHeader", () => {
  it("names the sort and the view switch", () => {
    render(
      <ResultHeader count={7} filters={FILTERS} onChange={vi.fn()} view="grid"
        onViewChange={vi.fn()} matchEnabled={false} />,
    );
    expect(screen.getByLabelText(en["filters.sortBy"])).toBeInTheDocument();
    expect(screen.getByRole("group", { name: en["filters.view"] })).toBeInTheDocument();
  });

  it("counts the whole filtered set", () => {
    render(
      <ResultHeader count={7} filters={FILTERS} onChange={vi.fn()} view="grid"
        onViewChange={vi.fn()} matchEnabled={false} />,
    );
    expect(screen.getByText("7 properties")).toBeInTheDocument();
  });

  it("drops a match sort the backend cannot honour", () => {
    const onChange = vi.fn();
    render(
      <ResultHeader count={7} filters={{ ...FILTERS, sort: "match" }} onChange={onChange}
        view="grid" onViewChange={vi.fn()} matchEnabled={false} />,
    );
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ sort: "newest" }));
  });

  it("keeps it when the score exists", () => {
    const onChange = vi.fn();
    render(
      <ResultHeader count={7} filters={{ ...FILTERS, sort: "match" }} onChange={onChange}
        view="grid" onViewChange={vi.fn()} matchEnabled />,
    );
    expect(onChange).not.toHaveBeenCalled();
  });
});
