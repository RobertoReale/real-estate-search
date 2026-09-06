/** Turning what is on the grid into a search that goes out to the portals.
 *
 *  The two sets of criteria are not the same set, and pretending otherwise is
 *  the bug this exists to avoid. A filter can ask for a deal score, a tag, a
 *  status or an area drawn on a map — none of which a portal has ever heard of
 *  — and a portal search can ask for things no filter carries. Prefilling one
 *  from the other as though the fields lined up would produce a search that
 *  quietly looks for half of what the user typed, which is worse than not
 *  offering the handover at all.
 *
 *  So every criterion that is set gets an answer here, and there are only three:
 *  it came across, it came across widened, or it could not go and this is why.
 *  `handoff.test.ts` holds the part that matters — every criterion the grid
 *  can show a chip for has one of the three, so nothing can be added to the rail
 *  and silently dropped on the way out.
 *
 *  A pure module: the address is a query string, and the screen at the other end
 *  reads it back rather than being handed component state.
 */
import { EMPTY_BUILDER } from "../../components/searchProfiles/constants";
import type { TranslationKey } from "../../i18n";
import type { PropertyFilters, SearchBuilderParams } from "../../types";
import { DEFAULT_FILTERS, SEARCHES, filtersFromSearch, searchFromState } from "../params";

/** The marker on the address that says these filters are a starting point for a
 *  search rather than a query in their own right. */
const FROM = "from";
const FILTERS = "filters";

/** What became of one criterion on the way to the portals. */
export type Carry = "exact" | "approximated" | "dropped";

export interface Criterion {
  /** The filter it came from — also the key of the chip that names it, which is
   *  where its label and its value come from. */
  key: string;
  carry: Carry;
  /** Why it was widened, or why it could not go. Absent only when it came
   *  across as it was. */
  note?: TranslationKey;
}

export interface Handoff {
  /** The filters that were on the grid, as the address carried them. */
  filters: PropertyFilters;
  /** The search form, prefilled with what maps. */
  params: SearchBuilderParams;
  /** One entry per criterion the user had set, in the order the chips list
   *  them. Nothing set is ever missing from it. */
  criteria: Criterion[];
}

/** The searches screen, opened with these filters as the starting point. */
export function handoffPath(filters: PropertyFilters): string {
  const params = searchFromState(filters, "grid");
  params.set(FROM, FILTERS);
  return `${SEARCHES}?${params}`;
}

/** The handover this address describes, or null if it is an ordinary visit to
 *  the searches screen. */
export function readHandoff(params: URLSearchParams): Handoff | null {
  if (params.get(FROM) !== FILTERS) return null;
  return fromFilters(filtersFromSearch(params));
}

export function fromFilters(filters: PropertyFilters): Handoff {
  // Buy/Rent is not a criterion — it is which market the user is in — so it is
  // carried without being listed, exactly as the chips leave it out.
  const params: SearchBuilderParams = {
    ...EMPTY_BUILDER,
    contract: filters.contract,
    city: filters.city,
    zone: filters.zone,
    min_price: filters.min_price,
    max_price: filters.max_price,
    min_sqm: filters.min_sqm,
  };

  const criteria: Criterion[] = [];
  function say(key: keyof PropertyFilters, carry: Carry, note?: TranslationKey) {
    const value = filters[key];
    if (value === DEFAULT_FILTERS[key] || value === "" || value === false) return;
    criteria.push({ key, carry, ...(note ? { note } : {}) });
  }

  // Free text is the one that looks most like it should map. It does not: it
  // matches the ad body of listings already collected, and the portals take a
  // place and a price instead.
  say("q", "dropped", "handoff.noteText");
  say("city", "exact");
  say("zone", "exact");
  say("min_price", "exact");
  say("max_price", "exact");
  say("min_sqm", "exact");
  say("max_sqm", "dropped", "handoff.noteMaxSqm");
  if (filters.rooms !== DEFAULT_FILTERS.rooms && filters.rooms !== "") {
    params.min_rooms = filters.rooms;
    criteria.push({ key: "rooms", carry: "approximated", note: "handoff.noteRooms" });
  }
  // The builder has a floor field and the backend reports it as one the portals
  // drop (`UNSUPPORTED_LABELS`), so filling it in would look like a criterion
  // and behave like none.
  say("floor_band", "dropped", "handoff.notePortal");
  say("status", "dropped", "handoff.noteLocal");
  say("source", "dropped", "handoff.noteLocal");
  say("tag", "dropped", "handoff.noteLocal");
  say("profile_id", "dropped", "handoff.noteLocal");
  say("only_price_drops", "dropped", "handoff.noteLocal");
  say("only_favorites", "dropped", "handoff.noteLocal");
  say("portal", "dropped", "handoff.noteLocal");
  say("agency", "dropped", "handoff.notePortal");
  say("deal", "dropped", "handoff.noteLocal");
  say("min_sqm_price", "dropped", "handoff.notePortal");
  say("max_sqm_price", "dropped", "handoff.notePortal");
  say("merged_only", "dropped", "handoff.noteLocal");
  say("geo_mode", "dropped", "handoff.noteArea");

  return { filters, params, criteria };
}
