/** The current query, read back as a list of things to undo.
 *
 *  The rail holds twenty-odd controls and most of them are shut inside it, so
 *  once it is collapsed — or on a phone, where it is a sheet — nothing on
 *  screen says why the grid is showing eleven properties instead of eighty. The
 *  chips are that answer, and each one carries the patch that removes it, so
 *  "why is this narrow" and "make it wider" are the same object.
 *
 *  A pure function on purpose: it is the part worth testing, and it is testable
 *  without a DOM. Two rules keep it honest.
 *
 *  - **Only what narrows the grid.** Buy/Rent is not a filter, it is which
 *    market the user is in, and Reset keeps it for the same reason. The sort
 *    does not narrow anything and is spelled out in the result header, where a
 *    chip would merely repeat it.
 *  - **The patch clears to the default, never to the empty string by hand.**
 *    `DEFAULT_FILTERS` is what `searchFromState` compares against when it
 *    decides what to write into the URL, so a chip that cleared to something
 *    else would leave `?status=` in the address forever.
 */
import type { TFunction, TranslationKey } from "../../i18n";
import type { PropertyFilters, SearchProfile } from "../../types";
import { groupSearchProfiles } from "../../utils/searchProfiles";
import { DEFAULT_FILTERS } from "../params";

export interface FilterChip {
  /** Stable across renders, and unique — React's key and the test's handle. */
  key: string;
  /** What the chip says, already translated. */
  label: string;
  /** The patch that takes this filter off. */
  clear: Partial<PropertyFilters>;
}

const FLOOR_BANDS: Record<string, TranslationKey> = {
  ground: "filters.floorGround", low: "filters.floorLow", mid: "filters.floorMid",
  high: "filters.floorHigh", top: "filters.floorTop",
};

const ORIGINS: Record<string, TranslationKey> = {
  scan: "filters.originScan", email: "filters.originEmail",
};

const DEALS: Record<string, TranslationKey> = {
  undervalued: "filters.dealUndervalued", fair_plus: "filters.dealFairPlus",
};

/** Statuses whose wording depends on the market: a sold flat and a rented one
 *  are the same row in the database and two different words to a reader. */
const STATUSES: Record<string, TranslationKey | [sale: TranslationKey, rent: TranslationKey]> = {
  active: ["filters.statusForSale", "filters.statusForRent"],
  filtered: "filters.statusFiltered",
  gone: "filters.statusGone",
  sold: ["filters.statusSold", "filters.statusRentedOut"],
  hidden: "filters.statusHidden",
  all: "filters.statusAll",
};

/** The portals name themselves; they are not translated anywhere else either. */
const PORTALS: Record<string, string> = {
  immobiliare: "Immobiliare", idealista: "Idealista",
};

export function activeFilterChips(
  filters: PropertyFilters,
  profiles: SearchProfile[],
  t: TFunction,
): FilterChip[] {
  const chips: FilterChip[] = [];

  /** A filter that carries a value: "City: Milano". */
  function valued(key: keyof PropertyFilters, labelKey: TranslationKey, shown?: string) {
    const value = filters[key];
    if (value === DEFAULT_FILTERS[key] || value === "" || value === false) return;
    const label = t(labelKey);
    chips.push({
      key,
      label: t("filters.chipValue", { label, value: shown ?? String(value) }),
      clear: { [key]: DEFAULT_FILTERS[key] } as Partial<PropertyFilters>,
    });
  }

  /** A filter that is simply on: "Price drops". */
  function flag(key: "only_price_drops" | "only_favorites" | "merged_only", labelKey: TranslationKey) {
    if (!filters[key]) return;
    chips.push({ key, label: t(labelKey), clear: { [key]: false } });
  }

  valued("q", "filters.search");
  valued("city", "filters.city");
  valued("zone", "filters.zone");
  valued("min_price", "filters.minPrice");
  valued("max_price", "filters.maxPrice");
  valued("min_sqm", "filters.minSqm");
  valued("max_sqm", "filters.maxSqm");
  valued("rooms", "filters.rooms");

  const band = FLOOR_BANDS[filters.floor_band];
  if (band) valued("floor_band", "filters.floor", t(band));

  const status = STATUSES[filters.status];
  if (status !== undefined) {
    const key = Array.isArray(status) ? status[filters.contract === "rent" ? 1 : 0] : status;
    valued("status", "filters.status", t(key));
  }

  const origin = ORIGINS[filters.source];
  if (origin) valued("source", "filters.origin", t(origin));

  valued("tag", "filters.tag");

  if (filters.profile_id) {
    // The select offers one entry per *group* of saved searches — the same
    // search run against two portals is one thing to the user — so the chip has
    // to name the group rather than the row behind it.
    const group = groupSearchProfiles(profiles)
      .find((g) => String(g.ids[0]) === filters.profile_id);
    valued("profile_id", "filters.limitToSearch", group?.baseName ?? filters.profile_id);
  }

  flag("only_price_drops", "filters.priceDrops");
  flag("only_favorites", "filters.favorites");

  const portal = PORTALS[filters.portal];
  if (portal) valued("portal", "filters.portal", portal);
  valued("agency", "filters.agency");
  const deal = DEALS[filters.deal];
  if (deal) valued("deal", "filters.deal", t(deal));
  valued("min_sqm_price", "filters.minSqmPrice");
  valued("max_sqm_price", "filters.maxSqmPrice");
  flag("merged_only", "filters.chipMerged");

  // The map's radius and polygon are drawn rather than typed, so there is no
  // control to go back to and clear: without a chip, a shape drawn on the map
  // and then left behind on the grid is a filter with no off switch.
  if (filters.geo_mode) {
    chips.push({
      key: "geo_mode",
      label: t("filters.chipMapArea"),
      clear: { geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "" },
    });
  }

  return chips;
}
