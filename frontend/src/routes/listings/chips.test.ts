/** The chips are the only readable statement of the query once the rail is
 *  shut, so what they leave out matters as much as what they say — and each one
 *  has to actually undo the filter it names.
 */

import { describe, expect, it } from "vitest";
import { activeFilterChips } from "./chips";
import { en } from "../../i18n/en";
import type { TranslationKey } from "../../i18n";
import { DEFAULT_FILTERS } from "../params";
import type { PropertyFilters } from "../../types";

/** The dictionary itself, interpolated the way `useT` does, so a chip that
 *  names a key the dictionary does not have fails here rather than rendering
 *  the key on screen. */
const t = (key: TranslationKey, vars?: Record<string, string | number>) =>
  Object.entries(vars ?? {}).reduce(
    (s, [k, v]) => s.replace(`{${k}}`, String(v)),
    en[key],
  );

const chips = (over: Partial<PropertyFilters> = {}) =>
  activeFilterChips({ ...DEFAULT_FILTERS, ...over }, [], t);

describe("activeFilterChips", () => {
  it("says nothing about a query that narrows nothing", () => {
    expect(chips()).toEqual([]);
  });

  it("ignores the market and the sort, which are not filters", () => {
    expect(chips({ contract: "rent", sort: "cheapest" })).toEqual([]);
  });

  it("names a value filter with its value", () => {
    expect(chips({ city: "Milano" })).toEqual([
      { key: "city", label: "City: Milano", clear: { city: "" } },
    ]);
  });

  it("translates the coded values rather than printing the code", () => {
    expect(chips({ floor_band: "ground" })[0].label).toBe("Floor: Ground floor");
    expect(chips({ source: "email" })[0].label).toBe("Origin: Email import");
    expect(chips({ portal: "idealista" })[0].label).toBe("Portal: Idealista");
  });

  it("words the status for the market it is read in", () => {
    expect(chips({ status: "sold" })[0].label).toBe("Status: Sold");
    expect(chips({ status: "sold", contract: "rent" })[0].label).toBe("Status: Rented out");
  });

  it("states a flag rather than giving it a value", () => {
    expect(chips({ only_favorites: true })).toEqual([
      { key: "only_favorites", label: en["filters.favorites"], clear: { only_favorites: false } },
    ]);
  });

  it("clears the whole shape behind a map area, not just the mode", () => {
    // A radius left in the URL with the mode cleared is a filter that is still
    // applied and no longer visible anywhere.
    const [chip] = chips({ geo_mode: "radius", center_lat: "45.4", center_lng: "9.2", radius_m: "2000" });
    expect(chip.clear).toEqual({
      geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
    });
  });

  it("clears to the default, so nothing is left in the address bar", () => {
    for (const chip of chips({ status: "gone", city: "Milano", rooms: "3" })) {
      for (const [key, value] of Object.entries(chip.clear)) {
        expect(value, `${chip.key} clears ${key} to something the URL keeps`)
          .toEqual(DEFAULT_FILTERS[key as keyof PropertyFilters]);
      }
    }
  });

  it("keeps its keys unique, which is what React indexes them by", () => {
    const keys = chips({
      city: "Milano", zone: "Navigli", min_price: "100000", max_price: "300000",
      rooms: "3", status: "gone", only_favorites: true, merged_only: true,
      geo_mode: "radius",
    }).map((c) => c.key);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
