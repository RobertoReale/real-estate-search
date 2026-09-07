/** Static option sets for the search-profile forms.
 *
 * `UNSUPPORTED_LABELS` is the one that needs watching: it must stay in step
 * with `search_builder.idealista_unsupported`, or the form will quietly promise
 * a filter Idealista cannot apply.
 */

import type { TranslationKey } from "../../i18n";
import type { SearchBuilderParams } from "../../types";

// How `last_run_status` reads to a user is `routes/searches/health.ts` now: it
// is one of the inputs to a search's state rather than a lookup of its own, and
// the map that used to be here could not see that a search switched off eleven
// days ago was still reporting the "OK" it left on.

export const EMPTY_BUILDER: SearchBuilderParams = {
  city: "", province: "", zone: "", zones: [], zone_ids: [], contract: "sale",
  min_price: "", max_price: "", min_rooms: "", max_rooms: "", min_sqm: "",
  balcony: false, garden: false, parking: false, elevator: false,
  exclude_auctions: false, pool: false, floor: "", condition: "",
  drawn_area: null,
};

/** Feature filters both portals can apply. */
export const FEATURES = [
  ["balcony", "profiles.featBalcony"],
  ["garden", "profiles.featGarden"],
  ["parking", "profiles.featParking"],
  ["elevator", "profiles.featElevator"],
  ["exclude_auctions", "profiles.featExcludeAuctions"],
  ["pool", "profiles.featPool"],
] as const satisfies readonly (readonly [string, TranslationKey])[];

/** Backend filter keys → what to call them when Idealista cannot apply them.
 *  Kept in step with search_builder.idealista_unsupported. */
export const UNSUPPORTED_LABELS: Record<string, TranslationKey> = {
  floor: "profiles.unsupportedFloor",
  condition: "profiles.unsupportedCondition",
  max_rooms: "profiles.unsupportedMaxRooms",
  drawn_area: "profiles.unsupportedDrawnArea",
};

export const FLOORS = [
  ["", "profiles.floorAny"],
  ["ground", "profiles.floorGround"],
  ["middle", "profiles.floorMiddle"],
  ["top", "profiles.floorTop"],
] as const satisfies readonly (readonly [string, TranslationKey])[];

export const CONDITIONS = [
  ["", "profiles.condAny"],
  ["new", "profiles.condNew"],
  ["good", "profiles.condGood"],
  ["excellent", "profiles.condExcellent"],
  ["to_renovate", "profiles.condToRenovate"],
] as const satisfies readonly (readonly [string, TranslationKey])[];

export const ASSISTANT_EXAMPLES = [
  "trilocale in affitto a Milano sotto i 1.200 € al mese",
  "bilocale a Milano zona Navigli o trilocale zona Lambrate, max 400k",
  "casa a Sesto San Giovanni (MI) almeno 90 mq, budget 280 mila",
];
