/** What was read, and what each portal will actually receive.
 *
 *  Pasting a link used to go straight from parse to fill to generate, with no
 *  moment that said *this is the search that will run*. The app already held
 *  most of that answer and kept it: `build_search_urls` reports which filters
 *  Idealista's URL grammar cannot express and whether the zone resolved to the
 *  portal's own page or to free text. Unsaid, the Idealista half of a paired
 *  search is quietly the wider one, and the extra listings read weeks later as
 *  a deduplication bug rather than as a filter that was never applied.
 *
 *  Four rules hold this screen together, and each one is a defect that already
 *  happened:
 *
 *  - **The two portals are never merged into one summary.** The difference
 *    between them is the entire point; a single combined line would hide it.
 *  - **Nothing is invented.** A criterion nothing was read for says so, in a
 *    style of its own, because a blank cell and a cell reading "the whole city"
 *    mean opposite things and looked identical.
 *  - **The area is named.** A polygon or a radius has no field in the builder
 *    form, so this is the only place it can be spoken about at all — "an area
 *    drawn on the map, 24 points" rather than silence or a guessed comune.
 *  - **The review is offline.** Everything below is derived from the parse and
 *    the built URLs; the one live Idealista request is a button the user
 *    presses. On a blocked day the review still reads correctly.
 */

import { useT, type TFunction, type TranslationKey } from "../../i18n";
import { LimitInline } from "../Limit";
import { PortalBadge } from "../PortalBadge";
import type { SearchBuilderParams, SearchBuilderUrls, SearchProfileParams } from "../../types";
import { CONDITIONS, FEATURES, FLOORS } from "./constants";
import { statesDrawnArea } from "./helpers";
import { Button, Checkbox, cx } from "../../ui";
import { Close, DrawnArea, Success, Verify, Warning } from "../../ui/icons";

/** One line of the review. Coarser than a field on purpose: a price band is one
 *  decision the user made, not two, and splitting it into `min_price` and
 *  `max_price` would turn a nine-line summary into a twenty-line form. */
export type ReviewRowId =
  | "where" | "zones" | "area" | "contract" | "price" | "rooms" | "sqm"
  | (typeof FEATURES)[number][0]
  | "floor" | "condition";

/** Every criterion the backend can extract, and the line that speaks for it.
 *
 *  Exhaustive by type, and that is the guarantee: a filter added to
 *  `SearchBuilderParamsOut` regenerates `types/api.ts`, widens
 *  `SearchProfileParams`, and fails to compile here until it has been given a
 *  line. `SearchReview.test.tsx` makes the same check against the generated
 *  file at runtime, for the case where the two drift the other way. Without it
 *  a new filter would be applied by the scan and mentioned by nothing. */
export const FIELD_ROW: Record<keyof SearchProfileParams, ReviewRowId> = {
  city: "where",
  province: "where",
  zone: "zones",
  zones: "zones",
  zone_ids: "zones",
  drawn_area: "area",
  contract: "contract",
  min_price: "price",
  max_price: "price",
  min_rooms: "rooms",
  max_rooms: "rooms",
  min_sqm: "sqm",
  balcony: "balcony",
  garden: "garden",
  parking: "parking",
  elevator: "elevator",
  exclude_auctions: "exclude_auctions",
  pool: "pool",
  floor: "floor",
  condition: "condition",
};

/** What one portal does with one criterion. Three honest states and an absence:
 *  `exact` carried it across, `approx` carried something wider (and says what),
 *  `dropped` could not carry it at all (and says why), `absent` means the
 *  search never asked for it. */
export interface Carry {
  state: "exact" | "approx" | "dropped" | "absent";
  why?: string;
}

export interface ReviewRow {
  id: ReviewRowId;
  label: string;
  /** What was read, already in words. Never empty when `undetected` is false. */
  detected: string;
  /** Nothing was read for this criterion — distinct from reading it as empty,
   *  which is a decision ("the whole city", "not requested") rather than a gap. */
  undetected: boolean;
  immobiliare: Carry;
  idealista: Carry;
}

const EXACT: Carry = { state: "exact" };
const ABSENT: Carry = { state: "absent" };

/** Which line each key of `idealista_unsupported` belongs to, and how to say it.
 *  Kept in step with `search_builder.idealista_unsupported`. */
const IDEALISTA_DROPS: Record<string, { row: ReviewRowId; why: TranslationKey }> = {
  max_rooms: { row: "rooms", why: "profiles.review.whyMaxRooms" },
  floor: { row: "floor", why: "profiles.review.whyFloor" },
  condition: { row: "condition", why: "profiles.review.whyCondition" },
  drawn_area: { row: "area", why: "profiles.review.whyDrawnArea" },
};

function label(options: readonly (readonly [string, TranslationKey])[], value: string, t: TFunction) {
  const found = options.find(([key]) => key === value);
  return found ? t(found[1]) : value;
}

/** A band in words. Both ends, one end, or nothing at all. */
function band(t: TFunction, min: string, max: string, unit: string): string {
  if (min && max) return t("profiles.review.between", { min, max, unit });
  if (min) return t("profiles.review.atLeast", { value: min, unit });
  if (max) return t("profiles.review.atMost", { value: max, unit });
  return "";
}

/** The drawn area in a sentence, never as coordinates.
 *
 *  `search_builder.drawn_area_summary` already reduced the shape to its kind
 *  and its size for exactly this: the review needs to say what kind of area
 *  this is, and a couple of hundred corner coordinates say it to nobody. */
export function areaText(area: SearchProfileParams["drawn_area"], t: TFunction): string {
  if (!area) return "";
  return area.kind === "polygon"
    ? t("profiles.review.areaPolygon", { points: area.points })
    : t("profiles.review.areaCircle", { radius: area.radius_m });
}

/** The review, as data. Pure, so the structural test can assert over it without
 *  a DOM and the component below has only rendering left to get wrong. */
export function reviewRows(
  params: SearchBuilderParams,
  built: SearchBuilderUrls,
  t: TFunction,
): ReviewRow[] {
  const city = params.city.trim();
  const province = params.province.trim();
  const zoneNames = [...params.zones, ...params.zone_ids];
  const zoned = zoneNames.length > 0;
  const area = params.drawn_area;

  // Idealista's own admission, indexed by the line that has to carry it. Read
  // off the response rather than re-derived here: the backend owns the rule,
  // and a second copy of it would be a second thing to keep true.
  const dropped = new Map<ReviewRowId, string>();
  for (const key of built.idealista_unsupported ?? []) {
    const drop = IDEALISTA_DROPS[key];
    if (drop) dropped.set(drop.row, t(drop.why));
  }
  const idealista = (row: ReviewRowId, asked: boolean): Carry => {
    const why = dropped.get(row);
    if (!asked) return ABSENT;
    return why ? { state: "dropped", why } : EXACT;
  };

  // Immobiliare carries every zone it was given as ids; names are the lossy
  // case, and `zone_warnings` is the backend saying which ones it had to leave
  // behind. The wording is rebuilt here rather than shown as it arrives,
  // because those sentences are English and this interface is not.
  const immobiliareZones: Carry = !zoned
    ? ABSENT
    : built.zone_warnings.length === 0
      ? EXACT
      : params.zones.length > 1 && params.zone_ids.length === 0
        ? {
          state: "approx",
          why: t("profiles.review.whyOneZoneName", {
            zone: params.zone, others: params.zones.length - 1,
          }),
        }
        : { state: "approx", why: t("profiles.review.whyTooManyZones", { count: params.zone_ids.length }) };

  const rows: ReviewRow[] = [
    {
      id: "where",
      label: t("profiles.review.rowWhere"),
      detected: [city, province && `(${province})`].filter(Boolean).join(" "),
      undetected: !city,
      immobiliare: city ? EXACT : ABSENT,
      idealista: city ? EXACT : ABSENT,
    },
    {
      id: "zones",
      label: t("profiles.review.rowZones"),
      // A search with a city and no zones is not a gap in the reading: it
      // covers the whole comune, and saying so is what stops a city-wide
      // search from being mistaken for a zone one.
      detected: zoned ? zoneNames.join(", ") : city ? t("profiles.review.wholeCity") : "",
      undetected: !zoned && !city,
      immobiliare: immobiliareZones,
      idealista: !zoned
        ? ABSENT
        : built.idealista_zone_page
          ? EXACT
          : { state: "approx", why: t("profiles.review.whyZoneFreeText") },
    },
    {
      id: "area",
      label: t("profiles.review.rowArea"),
      detected: areaText(area, t),
      undetected: false,
      // The URL about to be saved is the one that decides. A pasted link
      // carries the shape; the same search rebuilt from the form cannot, since
      // the builder has no field to rebuild it from.
      immobiliare: !area
        ? ABSENT
        : statesDrawnArea(built.immobiliare)
          ? EXACT
          : { state: "dropped", why: t("profiles.review.whyAreaRebuilt") },
      idealista: idealista("area", Boolean(area)),
    },
    {
      id: "contract",
      label: t("common.contract"),
      detected: t(params.contract === "rent" ? "filters.rent" : "filters.buy"),
      undetected: false,
      immobiliare: EXACT,
      idealista: EXACT,
    },
    {
      id: "price",
      label: t("profiles.review.rowPrice"),
      detected: band(t, params.min_price, params.max_price, "€"),
      undetected: !params.min_price && !params.max_price,
      immobiliare: params.min_price || params.max_price ? EXACT : ABSENT,
      idealista: idealista("price", Boolean(params.min_price || params.max_price)),
    },
    {
      id: "rooms",
      label: t("profiles.review.rowRooms"),
      detected: band(t, params.min_rooms, params.max_rooms, t("profiles.review.unitRooms")),
      undetected: !params.min_rooms && !params.max_rooms,
      immobiliare: params.min_rooms || params.max_rooms ? EXACT : ABSENT,
      idealista: idealista("rooms", Boolean(params.min_rooms || params.max_rooms)),
    },
    {
      id: "sqm",
      label: t("profiles.review.rowSqm"),
      detected: band(t, params.min_sqm, "", "m²"),
      undetected: !params.min_sqm,
      immobiliare: params.min_sqm ? EXACT : ABSENT,
      idealista: idealista("sqm", Boolean(params.min_sqm)),
    },
    ...FEATURES.map(([key, featureLabel]): ReviewRow => ({
      id: key,
      label: t(featureLabel),
      // A checkbox left off is a search that did not ask for it, not a reading
      // that failed — so this line never renders as "not detected".
      detected: t(params[key] ? "profiles.review.requested" : "profiles.review.notRequested"),
      undetected: false,
      immobiliare: params[key] ? EXACT : ABSENT,
      idealista: idealista(key, params[key]),
    })),
    {
      id: "floor",
      label: t("filters.floor"),
      detected: params.floor ? label(FLOORS, params.floor, t) : "",
      undetected: !params.floor,
      immobiliare: params.floor ? EXACT : ABSENT,
      idealista: idealista("floor", Boolean(params.floor)),
    },
    {
      id: "condition",
      label: t("profiles.condition"),
      detected: params.condition ? label(CONDITIONS, params.condition, t) : "",
      undetected: !params.condition,
      immobiliare: params.condition ? EXACT : ABSENT,
      idealista: idealista("condition", Boolean(params.condition)),
    },
  ];
  return rows;
}

const CARRY_TONE: Record<Carry["state"], string> = {
  exact: "t-muted",
  approx: "text-caution-ink",
  dropped: "accent-bad",
  absent: "t-dim",
};

function CarryCell({ carry }: { carry: Carry }) {
  const t = useT();
  if (carry.state === "absent") {
    return <span className="t-dim" aria-label={t("profiles.review.notInSearch")}>—</span>;
  }
  const Icon = carry.state === "exact" ? Success : carry.state === "approx" ? Warning : Close;
  const body = (
    <span className={cx("flex items-start gap-1.5", CARRY_TONE[carry.state])}>
      <Icon className="shrink-0 mt-0.5" />
      <span>
        {t(carry.state === "exact" ? "profiles.review.exact"
          : carry.state === "approx" ? "profiles.review.approx"
            : "profiles.review.dropped")}
        {carry.why ? <span className="block t-dim">{carry.why}</span> : null}
      </span>
    </span>
  );
  if (carry.state === "exact") return body;
  // Rule 8: an approximation and a loss are both limits, and both are stated
  // where they bite rather than on a page nobody opens.
  return (
    <LimitInline id={carry.state === "approx" ? "profiles.reviewApprox" : "profiles.reviewDropped"}>
      {body}
    </LimitInline>
  );
}

export interface SearchReviewProps {
  params: SearchBuilderParams;
  built: SearchBuilderUrls;
  confirmed: boolean;
  setConfirmed: (value: boolean) => void;
  /** The one live Idealista request, as a press rather than a side effect. */
  verifyZone: () => void;
  verifying: boolean;
}

export function SearchReview({
  params, built, confirmed, setConfirmed, verifyZone, verifying,
}: SearchReviewProps) {
  const t = useT();
  const rows = reviewRows(params, built, t);
  const zoned = params.zones.length > 0 || params.zone_ids.length > 0;
  return (
    <div className="space-y-2">
      <p className="text-xs t-muted">{t("profiles.review.intro")}</p>
      <div className="rounded-xl panel divide-y divide-line">
        <div className="hidden sm:grid grid-cols-[10rem_1fr_1fr_1fr] gap-3 px-3 py-2 text-xs t-dim">
          <span />
          <span>{t("profiles.review.colDetected")}</span>
          <span><PortalBadge portal="immobiliare" /></span>
          <span><PortalBadge portal="idealista" /></span>
        </div>
        {rows.map((row) => (
          <div key={row.id} data-review-row={row.id}
            className="grid sm:grid-cols-[10rem_1fr_1fr_1fr] gap-1 sm:gap-3 px-3 py-2 text-xs">
            <span className="font-medium">{row.label}</span>
            {/* Vincolo: a criterion nothing was read for is never blank, and
                never looks like one that was read as empty. */}
            {row.undetected ? (
              <span data-review-undetected className="italic t-dim">
                {t("profiles.review.notDetected")}
              </span>
            ) : (
              <span className="break-words">{row.detected}</span>
            )}
            {/* Vincolo: two columns, never one merged verdict. The asymmetry
                between the portals is the reason this screen exists. */}
            <span className="flex gap-1.5 sm:contents">
              <span className="sm:hidden t-dim shrink-0">Immobiliare:</span>
              <CarryCell carry={row.immobiliare} />
            </span>
            <span className="flex gap-1.5 sm:contents">
              <span className="sm:hidden t-dim shrink-0">Idealista:</span>
              <CarryCell carry={row.idealista} />
            </span>
          </div>
        ))}
      </div>
      {params.drawn_area && (
        <p className="flex items-start gap-1.5 text-xs t-muted">
          <DrawnArea className="shrink-0 mt-0.5" /> {t("profiles.review.areaKept")}
        </p>
      )}
      {/* Vincolo: the review is complete offline. The live check is offered,
          never spent on its own — a blocked Idealista must not turn pasting a
          link into a failure about something other than the parameters. */}
      {zoned && (
        <Button data-action="profiles.review.verifyZone" variant="ghost" size="sm"
          onClick={verifyZone} disabled={verifying}>
          <Verify /> {verifying ? t("profiles.review.verifying") : t("profiles.review.verifyZone")}
        </Button>
      )}
      <Checkbox data-action="profiles.review.confirm" className="min-h-11 sm:min-h-0"
        label={t("profiles.review.confirm")} checked={confirmed}
        onCheckedChange={(v) => setConfirmed(v === true)} />
    </div>
  );
}
