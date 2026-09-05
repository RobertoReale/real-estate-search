/** That each language actually reaches the screen — both halves of it.
 *
 * `i18n.test.ts` checks the dictionaries as data: same keys, same
 * placeholders, nothing empty. That says nothing about the wiring, and the
 * wiring has two halves that fail independently:
 *
 *  - components read the hook (`useT`), and
 *  - `formatPrice`, `humanizeFloor` and MapView's raw-HTML tooltips read the
 *    module-level locale `I18nProvider` assigns **during render**.
 *
 * The second is the fragile one. It is a plain module variable set as a side
 * effect of rendering the provider, so it can silently go stale — and when it
 * does, the words switch language while the prices, dates and floor labels keep
 * formatting the old way. Nothing else in the suite would notice: the numbers
 * are still numbers and every key still exists.
 *
 * So this renders real components in both languages and asserts on the whole
 * rendered text, which is the only place the two halves meet.
 */

import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { I18nProvider, STORAGE_KEY } from "./index";
import { en } from "./en";
import { it as itDict } from "./it";
import PropertyCard from "../components/PropertyCard";
import { FilterRail, ResultHeader } from "../routes/listings";
import { WithQuery } from "../test/withQuery";
import type { Property, PropertyFilters } from "../types";

const FILTERS: PropertyFilters = {
  status: "active", contract: "rent", city: "", zone: "", q: "", source: "",
  profile_id: "", tag: "", min_price: "", max_price: "", min_sqm: "",
  max_sqm: "", floor_band: "", rooms: "", portal: "", agency: "", deal: "",
  min_sqm_price: "", max_sqm_price: "", merged_only: false, geo_mode: "",
  center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: false, sort: "newest",
};

// Deliberately awkward: no title (so the "untitled" fallback shows), a rented
// contract (so the price gains a per-month suffix), and "T" as the floor — the
// Italian portal abbreviation only `humanizeFloor` can read.
const PROPERTY = {
  id: 1, title: "", city: "Milano", zone: "", address: "", latitude: null,
  longitude: null, coordinate_source: "" as const,
  rooms: 3, floor: "T", sqm: 80, contract: "rent",
  current_min_price: 1200, first_price: 1500, image_url: "", status: "sold",
  filtered_reason: "", source: "scan", is_favorite: false, notes: "",
  area_median_sqm_price: null, area_median_scope: null,
  sqm_price_delta_pct: null, omi_min_sqm_price: null, omi_max_sqm_price: null,
  omi_semester: null, omi_stale: false, omi_zone_code: "",
  match_score: null, deal_score: null,
  deal_label: null, deal_reasons: null, expected_discount_pct: null,
  target_price_low: null, target_price_high: null,
  first_seen_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:00:00Z",
  sold_at: null, listings: [], price_history: [], tags: [], found_by: [],
  commutes: [],
} satisfies Property;

const noop = () => {};

/** Renders the rail, the result header and a card the way the listings screen
 *  composes them, in the chosen language, and hands back everything that reached
 *  the screen.
 *
 *  Spaces are normalised first: `Intl` separates a number from its currency
 *  symbol with U+00A0, so the Italian price is "1200 €" and a plain
 *  "1200 €" never matches it. That has nothing to do with what is being tested
 *  and is a trap worth removing once rather than escaping at each assertion. */
function screenTextIn(lang: "en" | "it"): string {
  localStorage.setItem(STORAGE_KEY, lang);
  const { container } = render(
    <I18nProvider>
      <WithQuery>
        <FilterRail filters={FILTERS} onChange={noop} count={7} profiles={[]} tags={[]} />
        <ResultHeader count={7} filters={FILTERS} onChange={noop} view="grid"
          onViewChange={noop} matchEnabled />
        <PropertyCard property={PROPERTY} onClick={noop} onQuickHide={noop}
          onToggleFavorite={noop} allTags={[]} onAddTag={noop} onRemoveTag={noop} />
      </WithQuery>
    </I18nProvider>,
  );
  return (container.textContent ?? "").replace(/\p{Zs}/gu, " ");
}

describe("the English UI", () => {
  beforeEach(() => localStorage.clear());

  it("renders its own words", () => {
    const text = screenTextIn("en");
    for (const key of ["filters.search", "filters.sortBy", "filters.statusForRent",
                       "card.untitled", "card.rentedOut"] as const) {
      expect(text, `missing ${key}`).toContain(en[key]);
    }
  });

  it("formats through the same locale the words came from", () => {
    const text = screenTextIn("en");
    expect(text).toContain("€1,200");                  // symbol first, grouped
    expect(text).toContain(en["common.perMonthSuffix"]);
    expect(text).toContain(en["floor.ground"]);        // humanizeFloor("T")
    expect(text).not.toContain(itDict["card.untitled"]);
  });
});

describe("the Italian UI", () => {
  beforeEach(() => localStorage.clear());

  it("renders its own words", () => {
    const text = screenTextIn("it");
    for (const key of ["filters.search", "filters.sortBy", "filters.statusForRent",
                       "card.untitled", "card.rentedOut"] as const) {
      expect(text, `missing ${key}`).toContain(itDict[key]);
    }
  });

  it("formats through the same locale the words came from", () => {
    // the half that has no hook: a stale module locale leaves an Italian screen
    // printing English-formatted prices and an English floor label
    const text = screenTextIn("it");
    // Symbol placement is the signal, not the thousands separator: Italian
    // CLDR sets minimumGroupingDigits=2, so a four-digit price is "1200 €"
    // with no separator at all (12000 does become "12.000 €"). Asserting on a
    // separator here would fail against perfectly correct output.
    expect(text).toContain("1200 €");             // symbol last
    expect(text).toContain(itDict["common.perMonthSuffix"]);
    expect(text).toContain(itDict["floor.ground"]);
    expect(text).not.toContain("€1,200");
  });

  it("leaks no English", () => {
    const text = screenTextIn("it");
    for (const key of ["filters.sortBy", "card.untitled", "floor.ground"] as const) {
      expect(text, `English "${en[key]}" reached the Italian UI`).not.toContain(en[key]);
    }
  });
});
