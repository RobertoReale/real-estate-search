/** Pure conversions between the shapes a search takes — the assistant's numbers,
 * a stored profile's criteria, the form's strings — plus the two small readers
 * the rows and forms share.
 */

import { useT, type TFunction } from "../../i18n";
import type { AssistantSearch, SearchBuilderParams, SearchProfile, Settings } from "../../types";
import { EMPTY_BUILDER } from "./constants";
import { Filtered } from "../../ui/icons";

/** The zone half of the form, from a list of names.
 *
 *  `zone` and `zones` are one criterion written twice — the list is what a
 *  portal selection actually is, the string is what every caller written before
 *  it reads — so they are only ever produced together, here. Blank and repeated
 *  names are dropped, mirroring `search_builder.zone_names`, or the two ends
 *  would disagree about how many zones were asked for. */
export function zonePatch(names: readonly string[]): Pick<SearchBuilderParams, "zone" | "zones"> {
  const zones: string[] = [];
  for (const name of names) {
    const trimmed = (name || "").trim();
    if (trimmed && !zones.includes(trimmed)) zones.push(trimmed);
  }
  return { zone: zones[0] ?? "", zones };
}

/** The assistant answers with numbers; the builder form holds strings. */
export function paramsFromAssistant(search: AssistantSearch): SearchBuilderParams {
  const str = (v: number | null) => (v === null ? "" : String(v));
  return {
    city: search.params.city,
    province: search.params.province,
    // a plain-language query names its zone, never one of the portal's ids
    ...zonePatch([search.params.zone]),
    zone_ids: [],
    contract: search.params.contract,
    min_price: str(search.params.min_price),
    max_price: str(search.params.max_price),
    min_rooms: str(search.params.min_rooms),
    max_rooms: str(search.params.max_rooms),
    min_sqm: str(search.params.min_sqm),
    balcony: false, garden: false, parking: false, elevator: false,
    exclude_auctions: false, pool: false, floor: "", condition: "",
  };
}

/** Convert extracted or stored profile criteria to form strings. */
export function paramsFromProfile(params?: SearchProfile["params"]): SearchBuilderParams {
  if (!params) return EMPTY_BUILDER;
  const str = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  return {
    city: params.city || "",
    province: params.province || "",
    // `zones` is the API's own list and `zone` its first element; reading the
    // string when the list is empty keeps a profile stored before the list
    // arrived from losing the one zone it did carry.
    ...zonePatch(params.zones?.length ? params.zones : [params.zone || ""]),
    // Ids reach the form untouched. They are the whole reason the field can no
    // longer be a single word: a URL built from Immobiliare's map carries the
    // selection as ids and no name at all, and rendering nothing for it is what
    // made a three-zone search read as a city-wide one.
    zone_ids: params.zone_ids ?? [],
    contract: params.contract || "sale",
    min_price: str(params.min_price),
    max_price: str(params.max_price),
    min_rooms: str(params.min_rooms),
    max_rooms: str(params.max_rooms),
    min_sqm: str(params.min_sqm),
    balcony: Boolean(params.balcony),
    garden: Boolean(params.garden),
    parking: Boolean(params.parking),
    elevator: Boolean(params.elevator),
    exclude_auctions: Boolean(params.exclude_auctions),
    pool: Boolean(params.pool),
    floor: (params.floor || "") as SearchBuilderParams["floor"],
    condition: (params.condition || "") as SearchBuilderParams["condition"],
  };
}

/** Auto-label for a profile created from a parsed search. */
export function searchLabel(search: AssistantSearch, t: TFunction): string {
  const p = search.params;
  return [
    t(p.contract === "rent" ? "profiles.labelRent" : "profiles.labelBuy"),
    p.city,
    p.zone,
    p.min_rooms ? t("profiles.labelRooms", { count: p.min_rooms }) : "",
  ].filter(Boolean).join(" · ");
}

/** Surfaces the globally excluded keywords (set once in Settings, applied to
 *  every search) next to the per-search field, so what gets discarded is
 *  visible where the user is looking instead of a separate modal. */
export function GlobalKeywordsHint({ settings }: { settings: Settings | null }) {
  const t = useT();
  const words = settings?.excluded_keywords ?? [];
  if (!words.length) return null;
  return (
    <p className="flex items-center gap-1 text-xs t-dim -mt-1.5">
      <Filtered className="shrink-0" />
      {t("profiles.globalKeywords", { words: words.join(", ") })}
    </p>
  );
}

/** The full set of keywords that discard a listing for this profile: global
 *  (Settings) plus this search's own extras, deduplicated case-insensitively
 *  so the same word set from both places doesn't read as doubled. */
export function combinedKeywords(profile: SearchProfile, settings: Settings | null): string[] {
  const own = profile.excluded_keywords.split(",").map((k) => k.trim()).filter(Boolean);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const kw of [...(settings?.excluded_keywords ?? []), ...own]) {
    const key = kw.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(kw);
  }
  return result;
}

/** A channel is "ready" only when it is enabled AND has the credentials it
 *  needs — mirroring the backend's own gating in notifier.py, so the UI
 *  never claims a delivery route that would silently drop messages. */
export function channelReadiness(settings: Settings | null) {
  return {
    telegram: Boolean(
      settings?.telegram_enabled &&
      settings.telegram_token_set &&
      settings.telegram_chat_id,
    ),
    email: Boolean(
      settings?.email_enabled && settings.smtp_host && settings.email_to,
    ),
  };
}
