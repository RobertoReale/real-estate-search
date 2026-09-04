/** The codec that makes a dashboard linkable.
 *
 * Pure enough to test without a browser, and worth testing without one: every
 * assertion here is about a link somebody sent to somebody else. A default that
 * leaks into the query string makes an unreadable URL out of an untouched
 * dashboard; a default that is dropped on the way back in silently hands the
 * recipient a different grid from the one the sender was looking at; and a value
 * that survives without being recognised is a stranger's text reaching the
 * backend through a field the form would never have allowed.
 */
import { describe, expect, it } from "vitest";
import {
  DEFAULT_FILTERS, filtersFromSearch, searchFromState, viewFromSearch, withSearch,
} from "./params";

describe("searchFromState", () => {
  it("writes nothing for an untouched dashboard", () => {
    expect(searchFromState(DEFAULT_FILTERS, "grid").toString()).toBe("");
  });

  it("writes only what was chosen", () => {
    const params = searchFromState({ ...DEFAULT_FILTERS, city: "Milano", max_price: "500000" }, "grid");
    expect(params.toString()).toBe("city=Milano&max_price=500000");
  });

  it("writes the same string for the same state, whatever order it was built in", () => {
    const a = searchFromState({ ...DEFAULT_FILTERS, max_price: "500000", city: "Milano" }, "grid");
    const b = searchFromState({ ...DEFAULT_FILTERS, city: "Milano", max_price: "500000" }, "grid");
    expect(a.toString()).toBe(b.toString());
  });

  it("names the view only when it is not the grid", () => {
    expect(searchFromState(DEFAULT_FILTERS, "map").toString()).toBe("view=map");
    expect(searchFromState(DEFAULT_FILTERS, "grid").has("view")).toBe(false);
  });

  it("writes a raised flag and omits a lowered one", () => {
    expect(searchFromState({ ...DEFAULT_FILTERS, only_favorites: true }, "grid").get("only_favorites"))
      .toBe("1");
    expect(searchFromState({ ...DEFAULT_FILTERS, only_favorites: false }, "grid").has("only_favorites"))
      .toBe(false);
  });
});

describe("filtersFromSearch", () => {
  it("reads an empty query string as the untouched dashboard", () => {
    expect(filtersFromSearch(new URLSearchParams())).toEqual(DEFAULT_FILTERS);
  });

  it("round-trips every field, so the URL can be the state rather than a copy", () => {
    const chosen = {
      ...DEFAULT_FILTERS,
      status: "hidden", contract: "rent" as const, city: "Milano", zone: "Navigli",
      q: "terrazzo", source: "scan" as const, profile_id: "3", tag: "da vedere",
      min_price: "100000", max_price: "500000", min_sqm: "60", max_sqm: "120",
      floor_band: "high" as const, rooms: "3",
      portal: "idealista" as const, agency: "Tecnocasa", deal: "undervalued" as const,
      min_sqm_price: "2000", max_sqm_price: "9000", merged_only: true,
      geo_mode: "radius" as const, center_lat: "45.46", center_lng: "9.19",
      radius_m: "1500", poly: "", only_price_drops: true, only_favorites: true,
      sort: "price_asc",
    };
    expect(filtersFromSearch(searchFromState(chosen, "grid"))).toEqual(chosen);
    expect(viewFromSearch(searchFromState(chosen, "map"))).toBe("map");
  });

  it("drops a value the app does not recognise instead of passing it on", () => {
    const params = new URLSearchParams(
      "contract=banana&source=nowhere&floor_band=roof&portal=casa&deal=amazing&geo_mode=blob&view=list",
    );
    const filters = filtersFromSearch(params);
    expect(filters.contract).toBe("sale");
    expect(filters.source).toBe("");
    expect(filters.floor_band).toBe("");
    expect(filters.portal).toBe("");
    expect(filters.deal).toBe("");
    expect(filters.geo_mode).toBe("");
    expect(viewFromSearch(params)).toBe("grid");
  });

  it("reads a flag as raised only when it says 1", () => {
    expect(filtersFromSearch(new URLSearchParams("only_favorites=1")).only_favorites).toBe(true);
    expect(filtersFromSearch(new URLSearchParams("only_favorites=0")).only_favorites).toBe(false);
    expect(filtersFromSearch(new URLSearchParams("only_favorites=yes")).only_favorites).toBe(false);
  });
});

describe("withSearch", () => {
  it("keeps the filters on the address, from either form of query string", () => {
    expect(withSearch("/listings", "?city=Milano")).toBe("/listings?city=Milano");
    expect(withSearch("/listings", "city=Milano")).toBe("/listings?city=Milano");
  });

  it("leaves a bare path bare", () => {
    expect(withSearch("/listings", "")).toBe("/listings");
    expect(withSearch("/listings", "?")).toBe("/listings");
  });
});
