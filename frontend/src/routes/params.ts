/** The dashboard's state, as an address.
 *
 *  Every filter, the sort and the view live in the query string, and this file
 *  is the only thing that knows how to read or write them. Three rules make the
 *  addresses worth sharing:
 *
 *  - **nothing at its default is written down.** `/listings` is the whole
 *    dashboard, and a link carries only what the sender actually chose — which
 *    is also what keeps the URL readable enough to paste into a message.
 *  - **a value the app does not recognise is dropped.** A query string is
 *    something a stranger can type, and `?contract=banana` must reach neither
 *    the query key nor the backend. The fields with a closed vocabulary are
 *    checked against it here; the open ones (a city, a price) are the backend's
 *    to validate, as they already are when they come from a form.
 *  - **it round-trips.** Read what was written and the filters are the same
 *    object, so the URL can be the state rather than a copy of it kept in step.
 */
import type { PropertyFilters, ViewMode } from "../types";

/** The dashboard with nothing chosen, and the reference the writer compares
 *  against. */
export const DEFAULT_FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "", zone: "", q: "", source: "",
  profile_id: "", tag: "", min_price: "", max_price: "", min_sqm: "",
  max_sqm: "", floor_band: "", rooms: "",
  portal: "", agency: "", deal: "", min_sqm_price: "", max_sqm_price: "",
  merged_only: false,
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: false, sort: "newest",
};

/** In the order they are declared above, which is the order they appear in the
 *  URL: the same state has to produce the same string every time, or two links
 *  to the same grid would look like two different places. */
export const FILTER_KEYS = Object.keys(DEFAULT_FILTERS) as (keyof PropertyFilters)[];

const CONTRACTS = ["sale", "rent"] as const;
const SOURCES = ["", "scan", "email"] as const;
const FLOOR_BANDS = ["", "ground", "low", "mid", "high", "top"] as const;
const PORTALS = ["", "immobiliare", "idealista"] as const;
const DEALS = ["", "undervalued", "fair_plus"] as const;
const GEO_MODES = ["", "radius", "polygon"] as const;
const VIEWS = ["grid", "map"] as const;

/** The four places, and the log that opens on top of them. Written as constants
 *  because they are also what a component navigates to: a path spelled out at
 *  the call site is one nobody renames with the route.
 *
 *  `LISTINGS` is first because it is the default: "/" and anything unrecognised
 *  land there, and a user with data therefore sees properties rather than
 *  configuration. */
export const LISTINGS = "/listings";
export const INSIGHTS = "/insights";
export const SEARCHES = "/searches";
export const SETTINGS = "/settings";
export const LOGS = "/logs";

/** The address of one property. What a link, a bookmark or a notification
 *  points at. */
export function propertyPath(id: number): string {
  return `${LISTINGS}/${id}`;
}

/** A path with the filters the user is currently looking at kept on it, from
 *  either form of query string (`location.search` carries the "?",
 *  `URLSearchParams.toString()` does not). */
export function withSearch(path: string, search: string): string {
  const query = search.replace(/^\?/, "");
  return query ? `${path}?${query}` : path;
}

function oneOf<T extends string>(
  params: URLSearchParams, key: string, allowed: readonly T[], fallback: T,
): T {
  const value = params.get(key);
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function flag(params: URLSearchParams, key: string, fallback: boolean): boolean {
  const value = params.get(key);
  return value === null ? fallback : value === "1";
}

function text(params: URLSearchParams, key: keyof PropertyFilters): string {
  return params.get(key) ?? (DEFAULT_FILTERS[key] as string);
}

/** The filters this address asks for. */
export function filtersFromSearch(params: URLSearchParams): PropertyFilters {
  return {
    status: text(params, "status"),
    contract: oneOf(params, "contract", CONTRACTS, DEFAULT_FILTERS.contract),
    city: text(params, "city"),
    zone: text(params, "zone"),
    q: text(params, "q"),
    source: oneOf(params, "source", SOURCES, DEFAULT_FILTERS.source),
    profile_id: text(params, "profile_id"),
    tag: text(params, "tag"),
    min_price: text(params, "min_price"),
    max_price: text(params, "max_price"),
    min_sqm: text(params, "min_sqm"),
    max_sqm: text(params, "max_sqm"),
    floor_band: oneOf(params, "floor_band", FLOOR_BANDS, DEFAULT_FILTERS.floor_band),
    rooms: text(params, "rooms"),
    portal: oneOf(params, "portal", PORTALS, DEFAULT_FILTERS.portal),
    agency: text(params, "agency"),
    deal: oneOf(params, "deal", DEALS, DEFAULT_FILTERS.deal),
    min_sqm_price: text(params, "min_sqm_price"),
    max_sqm_price: text(params, "max_sqm_price"),
    merged_only: flag(params, "merged_only", DEFAULT_FILTERS.merged_only),
    geo_mode: oneOf(params, "geo_mode", GEO_MODES, DEFAULT_FILTERS.geo_mode),
    center_lat: text(params, "center_lat"),
    center_lng: text(params, "center_lng"),
    radius_m: text(params, "radius_m"),
    poly: text(params, "poly"),
    only_price_drops: flag(params, "only_price_drops", DEFAULT_FILTERS.only_price_drops),
    only_favorites: flag(params, "only_favorites", DEFAULT_FILTERS.only_favorites),
    sort: text(params, "sort"),
  };
}

/** Grid or map. Grid is the default and is never written down. */
export function viewFromSearch(params: URLSearchParams): ViewMode {
  return oneOf(params, "view", VIEWS, "grid");
}

/** The query string for a state: what the user chose, and nothing else. */
export function searchFromState(filters: PropertyFilters, view: ViewMode): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value === DEFAULT_FILTERS[key]) continue;
    params.set(key, typeof value === "boolean" ? (value ? "1" : "0") : value);
  }
  if (view !== "grid") params.set("view", view);
  return params;
}
