/** Every filter control must answer to the label printed above it.
 *
 * The controls were written as a `<label>` followed by a sibling `<input>` with
 * nothing tying the two together, which renders identically and is announced as
 * an unnamed box: a screen-reader user tabbing the search bar heard "edit text,
 * blank" fourteen times over. `getByLabelText` only resolves through a real
 * association (`htmlFor`/`id`, or a wrapping label), so this test is exactly the
 * property that was missing.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FiltersBar from "./FiltersBar";
import { en } from "../i18n/en";
import type { PropertyFilters } from "../types";

const FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "", zone: "", q: "", source: "",
  profile_id: "", tag: "", min_price: "", max_price: "", min_sqm: "",
  max_sqm: "", floor_band: "", rooms: "",
  portal: "", agency: "", deal: "", min_sqm_price: "", max_sqm_price: "",
  merged_only: false,
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: false, sort: "newest",
};

function renderBar() {
  render(
    <FiltersBar
      filters={FILTERS}
      onChange={vi.fn()}
      count={0}
      view="grid"
      onViewChange={vi.fn()}
      profiles={[]}
      tags={[]}
      matchEnabled={false}
      onReset={vi.fn()}
    />,
  );
}

// The always-visible controls of the search bar, by the label the user reads.
// `min/maxPrice` carry a conditional "/month" suffix, so they are matched by
// prefix rather than exact text.
const LABELLED: (keyof typeof en)[] = [
  "filters.search", "filters.city", "filters.zone", "filters.minSqm",
  "filters.maxSqm", "filters.rooms", "filters.floor", "filters.sortBy",
  "filters.status", "filters.origin",
];

describe("FiltersBar labelling", () => {
  it("names every filter control", () => {
    renderBar();
    for (const key of LABELLED) {
      expect(
        screen.getByLabelText(en[key]),
        `no control is labelled "${en[key]}"`,
      ).toBeInTheDocument();
    }
    // the two whose label carries a suffix
    expect(screen.getByLabelText(/^Min price/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Max price/)).toBeInTheDocument();
  });

  it("names the button groups, which have no control to label", () => {
    // Buy/Rent, the export formats and the view switch are groups of buttons:
    // a <label> there points at nothing, so they carry role="group" instead.
    renderBar();
    for (const key of ["filters.market", "filters.export", "filters.view"] as const) {
      expect(screen.getByRole("group", { name: en[key] })).toBeInTheDocument();
    }
  });

  it("names the advanced filters once the panel is open", () => {
    render(
      <FiltersBar
        filters={{ ...FILTERS, portal: "idealista" }}  // opens the panel
        onChange={vi.fn()}
        count={0}
        view="grid"
        onViewChange={vi.fn()}
        profiles={[]}
        tags={[]}
        matchEnabled={false}
        onReset={vi.fn()}
      />,
    );
    for (const key of ["filters.portal", "filters.agency", "filters.deal",
                       "filters.minSqmPrice", "filters.maxSqmPrice"] as const) {
      expect(
        screen.getByLabelText(en[key]),
        `no control is labelled "${en[key]}"`,
      ).toBeInTheDocument();
    }
  });
});
