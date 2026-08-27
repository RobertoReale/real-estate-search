/** Pure conversions between the shapes a search takes — the assistant's numbers,
 * a stored profile's criteria, the form's strings — plus the two small readers
 * the rows and forms share.
 */

import { useT, type TFunction } from "../../i18n";
import type { AssistantSearch, SearchBuilderParams, SearchProfile, Settings } from "../../types";
import { EMPTY_BUILDER } from "./constants";

/** The assistant answers with numbers; the builder form holds strings. */
export function paramsFromAssistant(search: AssistantSearch): SearchBuilderParams {
  const str = (v: number | null) => (v === null ? "" : String(v));
  return {
    city: search.params.city,
    province: search.params.province,
    zone: search.params.zone,
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
    zone: params.zone || "",
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
    <p className="text-xs t-dim -mt-1.5">
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
