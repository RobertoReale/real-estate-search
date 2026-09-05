/** Every filter control must answer to the label printed above it.
 *
 * The controls were written as a `<label>` followed by a sibling `<input>` with
 * nothing tying the two together, which renders identically and is announced as
 * an unnamed box: a screen-reader user tabbing the search bar heard "edit text,
 * blank" fourteen times over. `getByLabelText` only resolves through a real
 * association (`htmlFor`/`id`, or a wrapping label), so this test is exactly the
 * property that was missing.
 *
 * It follows the controls from the filter bar into the rail, which is what the
 * rail is: the same fields, in a column, behind a toggle. The one thing to know
 * about running it is that jsdom reports a 1024px window, so `useMediaQuery`
 * resolves to the desktop shape and the fields are rendered inline rather than
 * inside a sheet — which is the shape a label assertion can see.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FilterRail from "./FilterRail";
import { en } from "../../i18n/en";
import { WithQuery } from "../../test/withQuery";
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

function renderRail(filters: PropertyFilters = FILTERS) {
  render(
    <WithQuery>
      <FilterRail filters={filters} onChange={vi.fn()} count={0} profiles={[]} tags={[]} />
    </WithQuery>,
  );
}

// The always-visible controls of the rail, by the label the user reads.
// `min/maxPrice` carry a conditional "/month" suffix, so they are matched by
// prefix rather than exact text.
const LABELLED: (keyof typeof en)[] = [
  "filters.search", "filters.city", "filters.zone", "filters.minSqm",
  "filters.maxSqm", "filters.rooms", "filters.floor",
  "filters.status", "filters.origin",
];

describe("FilterRail labelling", () => {
  it("names every filter control", () => {
    renderRail();
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
    // Buy/Rent and the export formats are groups of buttons: a <label> there
    // points at nothing, so they carry role="group" instead.
    renderRail();
    for (const key of ["filters.market", "filters.export"] as const) {
      expect(screen.getByRole("group", { name: en[key] })).toBeInTheDocument();
    }
  });

  it("names the advanced filters once the panel is open", () => {
    renderRail({ ...FILTERS, portal: "idealista" }); // a set advanced filter opens it
    for (const key of ["filters.portal", "filters.agency", "filters.deal",
                       "filters.minSqmPrice", "filters.maxSqmPrice"] as const) {
      expect(
        screen.getByLabelText(en[key]),
        `no control is labelled "${en[key]}"`,
      ).toBeInTheDocument();
    }
  });

  it("shuts, and takes the fields with it", () => {
    // The point of the rail: the query is a panel the reader can put away. If
    // the toggle left the fields mounted, the "collapsible" part would be a
    // repaint and the grid would never get the width back.
    renderRail();
    const toggle = screen.getByRole("button", { name: new RegExp(en["filters.title"]) });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle);
    expect(screen.queryByLabelText(en["filters.city"])).not.toBeInTheDocument();
  });
});
