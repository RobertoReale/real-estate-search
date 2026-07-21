import { useState } from "react";
import { formatNumber, useT } from "../i18n";
import { formatPrice } from "../services/api";
import { humanizeFloor } from "../utils/format";
import { PortalBadge } from "./PortalBadge";
import TagPicker from "./TagPicker";
import type { Property, Tag } from "../types";

interface Props {
  property: Property;
  onClick: () => void;
  onQuickHide: () => void;
  onToggleFavorite: () => void;
  selected?: boolean;
  onToggleSelect?: () => void;
  isNew?: boolean;
  allTags: Tag[];
  onAddTag: (name: string) => void;
  onRemoveTag: (tagId: number) => void;
}

/** Badge comparing this property's €/sqm to the local median.
 *  Only shown beyond ±5%: smaller deltas are market noise, not signal. */
export function MarketBadge({ property: p }: { property: Property }) {
  const t = useT();
  if (p.sqm_price_delta_pct === null || Math.abs(p.sqm_price_delta_pct) < 5) {
    return null;
  }
  const below = p.sqm_price_delta_pct < 0;
  const scope = t(p.area_median_scope === "zone" ? "card.scopeZone" : "card.scopeCity");
  const pct = Math.abs(p.sqm_price_delta_pct).toFixed(0);
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${
        below ? "chip-emerald" : "chip-amber"
      }`}
      title={t("card.medianIn", {
        scope,
        value: formatNumber(Math.round(p.area_median_sqm_price ?? 0)),
      })}>
      {t(below ? "card.belowAverage" : "card.aboveAverage", { pct, scope })}
    </span>
  );
}

/** "🎯 92% match" badge: compatibility with the user's "dream home" settings.
 *  Only rendered when the Smart Match Score feature is on (score is non-null).
 *  Colour tracks the score so a strong match reads at a glance. */
export function MatchBadge({ score }: { score: number | null }) {
  const t = useT();
  if (score === null || score === undefined) return null;
  const chip = score >= 80 ? "chip-emerald" : score >= 50 ? "chip-amber" : "chip-slate";
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${chip}`}
      title={t("card.matchBadgeTitle")}>
      {t("card.matchBadge", { score })}
    </span>
  );
}

/** "🎯 16% below market" badge from the Deal Score. Shown only when the
 *  verdict is decisive (undervalued/overpriced); "fair" adds no signal. A
 *  positive score means priced below the local market. */
export function DealBadge({ property: p }: { property: Property }) {
  const t = useT();
  if (p.deal_score === null || p.deal_label === "fair" || p.deal_label === null) {
    return null;
  }
  // The Deal Score's base is exactly the market-position delta (deal_score.py:
  // base = -sqm_price_delta_pct); condition/agency cues then shift it. When
  // nothing shifted it, this badge just restates the MarketBadge with the same
  // number in different words ("18% above market" next to "18% above city
  // average") — a confusing duplicate. Drop it in that case: the MarketBadge
  // already carries the €/sqm position, and DealBadge earns its place only when
  // it says something more (a renovation/agency adjustment moved the score).
  if (
    p.sqm_price_delta_pct !== null &&
    Math.round(-p.sqm_price_delta_pct) === p.deal_score
  ) {
    return null;
  }
  const under = p.deal_label === "undervalued";
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${
        under ? "chip-emerald" : "chip-amber"
      }`}
      title={(p.deal_reasons ?? []).join(" · ") || t("card.dealScore")}>
      {t(under ? "card.dealBelowMarket" : "card.dealAboveMarket", {
        pct: Math.abs(p.deal_score),
      })}
    </span>
  );
}

export default function PropertyCard({
  property: p, onClick, onQuickHide, onToggleFavorite, selected, onToggleSelect, isNew,
  allTags, onAddTag, onRemoveTag,
}: Props) {
  const t = useT();
  const drop =
    p.first_price && p.current_min_price && p.current_min_price < p.first_price
      ? ((p.current_min_price - p.first_price) / p.first_price) * 100
      : null;
  const sqmPrice =
    p.current_min_price && p.sqm ? Math.round(p.current_min_price / p.sqm) : null;
  const portals = [...new Set(p.listings.map((l) => l.portal))];
  // portal image URLs are often signed/expiring CDN links: a stale one fails
  // to load, and the browser's broken-image icon renders the alt text right
  // under the absolutely-positioned badges instead of the placeholder icon
  const [imgBroken, setImgBroken] = useState(false);

  return (
    <article
      onClick={onClick}
      className={`glass rounded-2xl overflow-hidden cursor-pointer group hover:border-blue-500/50 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-200 hover:-translate-y-0.5 ${
        selected ? "ring-2 ring-blue-500 border-blue-500" : ""
      }`}>
      <div className="relative h-44 bg-slate-200 dark:bg-slate-800 overflow-hidden">
        {p.image_url && !imgBroken ? (
          <img src={p.image_url} alt={p.title} loading="lazy"
            onError={() => setImgBroken(true)}
            className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-slate-400 dark:text-slate-600">
            🏠
          </div>
        )}
        {/* right padding reserves the quick-action corner, which is wider on
            phones where the buttons grow to a thumb-sized target */}
        <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 pr-28 sm:pr-24">
          {isNew && (
            <span
              className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-blue-600/90 text-white backdrop-blur"
              title={t("card.newTitle")}>
              {t("card.new")}
            </span>
          )}
          {portals.map((portal) => (
            <PortalBadge key={portal} portal={portal} variant="overlay" />
          ))}
          {p.contract === "rent" && (
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-teal-600/80 text-white backdrop-blur">
              {t("card.rent")}
            </span>
          )}
          {p.listings.length > 1 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-600/80 text-white backdrop-blur">
              {t("card.mergedListings", { count: p.listings.length })}
            </span>
          )}
          {p.source === "email" && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-600/80 text-white backdrop-blur"
              title={t("card.emailTitle")}>
              {t("card.email")}
            </span>
          )}
        </div>

        {/* quick actions: select + star + hide without opening the modal */}
        <div className="absolute top-2 right-2 flex gap-1.5"
          onClick={(e) => e.stopPropagation()}>
          {onToggleSelect && (
            <button
              type="button"
              className={`w-9 h-9 sm:w-7 sm:h-7 rounded-lg backdrop-blur flex items-center justify-center text-sm transition btn-focus ${
                selected
                  ? "bg-blue-600 text-white shadow"
                  : "bg-white/80 text-slate-400 dark:bg-slate-900/60 dark:text-slate-500 hover:text-blue-500"
              }`}
              title={selected ? t("card.deselect") : t("card.selectForBatch")}
              onClick={onToggleSelect}>
              {selected ? "✓" : "☐"}
            </button>
          )}
          <button
            className={`w-9 h-9 sm:w-7 sm:h-7 rounded-lg backdrop-blur flex items-center
              justify-center text-sm transition btn-focus ${
                p.is_favorite
                  ? "bg-yellow-500/90 text-white"
                  : "bg-white/80 text-slate-600 dark:bg-slate-900/60 dark:text-slate-300 hover:bg-yellow-500/70 hover:text-white dark:hover:bg-yellow-500/70 dark:hover:text-white"
              }`}
            title={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
            aria-label={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
            onClick={onToggleFavorite}>
            {p.is_favorite ? "★" : "☆"}
          </button>
          {p.status !== "hidden" && (
            <button
              className="w-9 h-9 sm:w-7 sm:h-7 rounded-lg bg-white/80 text-slate-600
                dark:bg-slate-900/60 dark:text-slate-300 backdrop-blur hover:bg-rose-600/80
                hover:text-white dark:hover:bg-rose-600/80 dark:hover:text-white flex
                items-center justify-center text-sm transition btn-focus"
              title={t("card.hideTitle")}
              aria-label={t("card.hideAria")}
              onClick={onQuickHide}>
              ✕
            </button>
          )}
        </div>

        <div className="absolute bottom-2 left-2 flex flex-wrap gap-1.5">
          {drop !== null && (
            <span className="text-xs font-bold px-2 py-1 rounded-lg bg-emerald-600/90 text-white backdrop-blur">
              📉 {drop.toFixed(1)}%
            </span>
          )}
          {p.status === "filtered" && (
            <span className="text-xs px-2 py-1 rounded-lg bg-rose-600/90 text-white backdrop-blur">
              {t("card.filteredReason", { reason: p.filtered_reason ?? "" })}
            </span>
          )}
          {p.status === "gone" && (
            <span className="text-xs px-2 py-1 rounded-lg bg-slate-600/90 text-white backdrop-blur">
              {t("card.noLongerAvailable")}
            </span>
          )}
          {p.status === "sold" && (
            <span className="text-xs font-bold px-2 py-1 rounded-lg bg-amber-600/90 text-white backdrop-blur">
              {t(p.contract === "rent" ? "card.rentedOut" : "card.sold")}
            </span>
          )}
        </div>
      </div>

      <div className="p-4">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xl font-bold accent-price">
            {formatPrice(p.current_min_price, p.contract)}
          </span>
          {sqmPrice && (
            <span className="text-xs t-muted">
              {t("common.sqmPrice", { value: formatNumber(sqmPrice) })}
            </span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5 empty:hidden">
          <DealBadge property={p} />
          <MatchBadge score={p.match_score} />
          <MarketBadge property={p} />
        </div>
        <div className="mt-1.5">
          <TagPicker tags={p.tags} allTags={allTags} onAdd={onAddTag} onRemove={onRemoveTag} compact />
        </div>
        <h3 className="font-medium text-sm mt-1 line-clamp-2 min-h-[2.5rem]">
          {p.title || t("card.untitled")}
        </h3>
        <p className="text-xs t-muted mt-1 truncate">
          📍 {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || t("card.locationUnknown")}
        </p>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs t-body">
          {p.rooms && <span>🚪 {t("common.rooms", { count: p.rooms })}</span>}
          {p.sqm && <span>📐 {t("common.sqm", { value: p.sqm.toFixed(0) })}</span>}
          {p.floor && <span>🏢 {humanizeFloor(p.floor)}</span>}
          {p.notes && <span title={p.notes}>{t("card.notes")}</span>}
          {/* Whether the property is placeable on the map. Called out because a
              zone filter silently drops the un-pinned ones (invariant 19), and
              from the grid there was no way to tell which cards those are. */}
          {(p.latitude === null || p.longitude === null) && (
            <span className="t-dim" title={t("card.notOnMapTitle")}>
              {t("card.notOnMap")}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
