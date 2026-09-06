/** A search that quietly looks for half of what the user asked for is worse
 *  than no handover at all, so the rule under test is coverage rather than
 *  wording: every criterion the grid can show a chip for gets an answer here.
 *
 *  The two lists are compared key by key. Add a filter to the rail without
 *  deciding what becomes of it on the way to the portals and this fails — which
 *  is the only moment anyone would think to.
 */

import { describe, expect, it } from "vitest";
import { fromFilters, handoffPath, readHandoff } from "./handoff";
import { activeFilterChips } from "../listings/chips";
import { en } from "../../i18n/en";
import type { TranslationKey } from "../../i18n";
import { DEFAULT_FILTERS } from "../params";
import type { PropertyFilters } from "../../types";

const t = (key: TranslationKey, vars?: Record<string, string | number>) =>
  Object.entries(vars ?? {}).reduce(
    (s, [k, v]) => s.replace(`{${k}}`, String(v)),
    en[key],
  );

/** Every filter the rail can set, all at once — the widest query the grid can
 *  express, and therefore the whole surface the handover has to answer for. */
const EVERYTHING: PropertyFilters = {
  ...DEFAULT_FILTERS,
  contract: "rent",
  q: "terrazzo",
  city: "Milano",
  zone: "Navigli",
  min_price: "800",
  max_price: "1600",
  min_sqm: "60",
  max_sqm: "120",
  rooms: "3",
  floor_band: "high",
  status: "gone",
  source: "email",
  tag: "da vedere",
  profile_id: "7",
  only_price_drops: true,
  only_favorites: true,
  portal: "idealista",
  agency: "Studio Rossi",
  deal: "undervalued",
  min_sqm_price: "10",
  max_sqm_price: "30",
  merged_only: true,
  geo_mode: "radius",
  center_lat: "45.4",
  center_lng: "9.2",
  radius_m: "2000",
  sort: "cheapest",
};

describe("fromFilters", () => {
  it("accounts for every criterion the grid can name", () => {
    const chipped = activeFilterChips(EVERYTHING, [], t).map((c) => c.key);
    const answered = fromFilters(EVERYTHING).criteria.map((c) => c.key);
    expect(answered, "a filter the rail can set has no fate on the way out")
      .toEqual(chipped);
  });

  it("says nothing about a query that narrows nothing", () => {
    expect(fromFilters(DEFAULT_FILTERS).criteria).toEqual([]);
  });

  it("carries the market, which is not a criterion but is not lost either", () => {
    expect(fromFilters(EVERYTHING).params.contract).toBe("rent");
  });

  it("prefills only the fields a portal search actually has", () => {
    const { params } = fromFilters(EVERYTHING);
    expect(params.city).toBe("Milano");
    expect(params.zone).toBe("Navigli");
    expect(params.min_price).toBe("800");
    expect(params.max_price).toBe("1600");
    expect(params.min_sqm).toBe("60");
  });

  it("widens the exact room count rather than dropping or faking it", () => {
    const { params, criteria } = fromFilters({ ...DEFAULT_FILTERS, rooms: "3" });
    expect(params.min_rooms).toBe("3");
    expect(criteria).toEqual([
      { key: "rooms", carry: "approximated", note: "handoff.noteRooms" },
    ]);
  });

  it("never lets a dropped criterion go unexplained", () => {
    for (const c of fromFilters(EVERYTHING).criteria) {
      if (c.carry === "exact") continue;
      expect(c.note, `${c.key} is not carried and does not say why`).toBeTruthy();
      expect(en[c.note as TranslationKey], `${c.note} is not in the dictionary`)
        .toBeTruthy();
    }
  });

  it("leaves the local-only criteria out of the search itself", () => {
    // The failure this exists to catch: a portal search built from the filters
    // "for convenience", quietly narrowed by things the portals never saw.
    const { params } = fromFilters(EVERYTHING);
    const text = JSON.stringify(params);
    for (const local of ["terrazzo", "da vedere", "Studio Rossi", "undervalued"]) {
      expect(text, `${local} reached the portal search`).not.toContain(local);
    }
  });
});

describe("the address the handover travels on", () => {
  it("survives the round trip through the URL", () => {
    const path = handoffPath(EVERYTHING);
    const read = readHandoff(new URLSearchParams(path.slice(path.indexOf("?"))));
    expect(read?.criteria).toEqual(fromFilters(EVERYTHING).criteria);
  });

  it("is nothing at all on an ordinary visit to the searches screen", () => {
    expect(readHandoff(new URLSearchParams(""))).toBeNull();
    expect(readHandoff(new URLSearchParams("?city=Milano"))).toBeNull();
  });
});
