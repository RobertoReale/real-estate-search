/** One statement per card, never two, and never one built out of the other's
 *  numbers. The card used to print the Deal Score and the median comparison
 *  side by side; these pin the precedence that replaced them, and pin that the
 *  OMI band takes no part in it (invariant 22).
 */
import { describe, expect, it } from "vitest";
import { marketPosition } from "./marketPosition";
import type { Property } from "../types";

/** A listing with no market signal at all. Each test turns on exactly the
 *  fields it is about, so what drives the outcome is visible in the test. */
const BASE = {
  id: 1, title: "Trilocale in Via Test", city: "Milano", zone: "Navigli",
  address: "", latitude: null, longitude: null, coordinate_source: "" as const,
  rooms: 3, floor: "2", sqm: 80,
  contract: "sale", current_min_price: 300000, first_price: 300000,
  image_url: "", status: "active", filtered_reason: "", source: "scan",
  is_favorite: false, notes: "", area_median_sqm_price: null,
  area_median_scope: null, sqm_price_delta_pct: null,
  omi_min_sqm_price: null, omi_max_sqm_price: null, omi_semester: null,
  omi_stale: false, omi_zone_code: "", match_score: null,
  deal_score: null, deal_label: null, deal_reasons: null,
  expected_discount_pct: null, target_price_low: null, target_price_high: null,
  first_seen_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:00:00Z",
  sold_at: null, listings: [], price_history: [], tags: [], found_by: [],
  commutes: [],
} satisfies Property;

function property(fields: Partial<Property>): Property {
  return { ...BASE, ...fields };
}

describe("marketPosition", () => {
  it("says nothing when the listing is at its market", () => {
    expect(marketPosition(property({ sqm_price_delta_pct: -2.4 }))).toBeNull();
    expect(marketPosition(BASE)).toBeNull();
  });

  it("reports the median comparison beyond ±5%", () => {
    const position = marketPosition(property({
      sqm_price_delta_pct: -12.4, area_median_scope: "zone",
      area_median_sqm_price: 4200,
    }));
    expect(position).toEqual({
      kind: "median", below: true, pct: 12, scope: "zone", median: 4200,
    });
  });

  it("falls back to the city when the zone had too few comparables", () => {
    const position = marketPosition(property({
      sqm_price_delta_pct: 9, area_median_scope: null,
    }));
    expect(position).toMatchObject({ kind: "median", below: false, scope: "city" });
  });

  it("prefers the Deal Score when a cue has moved it off the raw delta", () => {
    // base = -sqm_price_delta_pct = 10; condition/agency cues took it to 18
    const position = marketPosition(property({
      sqm_price_delta_pct: -10, area_median_sqm_price: 4200,
      deal_score: 18, deal_label: "undervalued", deal_reasons: ["renovated"],
    }));
    expect(position).toEqual({
      kind: "deal", under: true, pct: 18, reasons: ["renovated"],
    });
  });

  it("drops the Deal Score when it only restates the delta", () => {
    // nothing shifted the base, so the two badges carried the same number in
    // different words — the median comparison is the one that keeps its scope
    const position = marketPosition(property({
      sqm_price_delta_pct: -16, area_median_scope: "zone",
      deal_score: 16, deal_label: "undervalued",
    }));
    expect(position).toMatchObject({ kind: "median", below: true, pct: 16 });
  });

  it("ignores a 'fair' verdict, which adds nothing to a price", () => {
    expect(marketPosition(property({ deal_score: 2, deal_label: "fair" }))).toBeNull();
  });

  it("never reads the OMI band (invariant 22)", () => {
    // A listing whose only market data is the OMI band has no card statement:
    // the band is a different measure and is presented separately, labelled.
    const omiOnly = property({
      omi_min_sqm_price: 3000, omi_max_sqm_price: 4600, omi_semester: "2026-1",
      omi_zone_code: "D4",
    });
    expect(marketPosition(omiOnly)).toBeNull();
    // and widening the band changes nothing about the statement chosen
    const withMedian = property({ sqm_price_delta_pct: -8, area_median_scope: "zone" });
    expect(marketPosition({ ...withMedian, omi_min_sqm_price: 1, omi_max_sqm_price: 99999 }))
      .toEqual(marketPosition(withMedian));
  });
});
