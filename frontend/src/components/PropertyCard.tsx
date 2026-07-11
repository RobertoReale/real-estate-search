import { formatPrice } from "../services/api";
import { PortalBadge } from "./PortalBadge";
import type { Property } from "../types";

interface Props {
  property: Property;
  onClick: () => void;
  onQuickHide: () => void;
  onToggleFavorite: () => void;
}

/** Badge comparing this property's €/sqm to the local median.
 *  Only shown beyond ±5%: smaller deltas are market noise, not signal. */
export function MarketBadge({ property: p }: { property: Property }) {
  if (p.sqm_price_delta_pct === null || Math.abs(p.sqm_price_delta_pct) < 5) {
    return null;
  }
  const below = p.sqm_price_delta_pct < 0;
  const scope = p.area_median_scope === "zone" ? "neighborhood" : "city";
  return (
    <span
      className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${
        below ? "chip-emerald" : "chip-amber"
      }`}
      title={`Median in this ${scope}: ${Math.round(
        p.area_median_sqm_price ?? 0
      ).toLocaleString("en-IE")} €/sqm`}>
      {Math.abs(p.sqm_price_delta_pct).toFixed(0)}%{" "}
      {below ? "below" : "above"} {scope} average
    </span>
  );
}

/** "🎯 92% match" badge: compatibility with the user's "dream home" settings.
 *  Only rendered when the Smart Match Score feature is on (score is non-null).
 *  Colour tracks the score so a strong match reads at a glance. */
export function MatchBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) return null;
  const chip = score >= 80 ? "chip-emerald" : score >= 50 ? "chip-amber" : "chip-slate";
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-lg ${chip}`}
      title="Compatibility with your dream-home settings">
      🎯 {score}% match
    </span>
  );
}

export default function PropertyCard({
  property: p, onClick, onQuickHide, onToggleFavorite,
}: Props) {
  const drop =
    p.first_price && p.current_min_price && p.current_min_price < p.first_price
      ? ((p.current_min_price - p.first_price) / p.first_price) * 100
      : null;
  const sqmPrice =
    p.current_min_price && p.sqm ? Math.round(p.current_min_price / p.sqm) : null;
  const portals = [...new Set(p.listings.map((l) => l.portal))];

  return (
    <article
      onClick={onClick}
      className="glass rounded-2xl overflow-hidden cursor-pointer group
        hover:border-blue-500/50 hover:shadow-xl hover:shadow-blue-500/10
        transition-all duration-200 hover:-translate-y-0.5">
      <div className="relative h-44 bg-slate-200 dark:bg-slate-800 overflow-hidden">
        {p.image_url ? (
          <img src={p.image_url} alt={p.title} loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-4xl text-slate-400 dark:text-slate-600">
            🏠
          </div>
        )}
        {/* right padding reserves the quick-action corner, which is wider on
            phones where the buttons grow to a thumb-sized target */}
        <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 pr-20 sm:pr-16">
          {portals.map((portal) => (
            <PortalBadge key={portal} portal={portal} variant="overlay" />
          ))}
          {p.contract === "rent" && (
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-teal-600/80 text-white backdrop-blur">
              🔑 rent
            </span>
          )}
          {p.listings.length > 1 && (
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-600/80 text-white backdrop-blur">
              {p.listings.length} merged listings
            </span>
          )}
        </div>

        {/* quick actions: star + hide without opening the modal */}
        <div className="absolute top-2 right-2 flex gap-1.5"
          onClick={(e) => e.stopPropagation()}>
          <button
            className={`w-9 h-9 sm:w-7 sm:h-7 rounded-lg backdrop-blur flex items-center
              justify-center text-sm transition btn-focus ${
                p.is_favorite
                  ? "bg-yellow-500/90 text-white"
                  : "bg-white/80 text-slate-600 dark:bg-slate-900/60 dark:text-slate-300 hover:bg-yellow-500/70 hover:text-white dark:hover:bg-yellow-500/70 dark:hover:text-white"
              }`}
            title={p.is_favorite ? "Remove from favorites" : "Add to favorites"}
            aria-label={p.is_favorite ? "Remove from favorites" : "Add to favorites"}
            onClick={onToggleFavorite}>
            {p.is_favorite ? "★" : "☆"}
          </button>
          {p.status !== "hidden" && (
            <button
              className="w-9 h-9 sm:w-7 sm:h-7 rounded-lg bg-white/80 text-slate-600
                dark:bg-slate-900/60 dark:text-slate-300 backdrop-blur hover:bg-rose-600/80
                hover:text-white dark:hover:bg-rose-600/80 dark:hover:text-white flex
                items-center justify-center text-sm transition btn-focus"
              title="Hide this property (it will never come back on its own)"
              aria-label="Hide this property"
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
              🚫 Filtered: {p.filtered_reason}
            </span>
          )}
          {p.status === "gone" && (
            <span className="text-xs px-2 py-1 rounded-lg bg-slate-600/90 text-white backdrop-blur">
              💨 No longer available
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
              {sqmPrice.toLocaleString("en-IE")} €/sqm
            </span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5 empty:hidden">
          <MatchBadge score={p.match_score} />
          <MarketBadge property={p} />
        </div>
        <h3 className="font-medium text-sm mt-1 line-clamp-2 min-h-[2.5rem]">
          {p.title || "Untitled"}
        </h3>
        <p className="text-xs t-muted mt-1 truncate">
          📍 {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || "Location N/A"}
        </p>
        <div className="flex gap-3 mt-2 text-xs t-body">
          {p.rooms && <span>🚪 {p.rooms} rooms</span>}
          {p.sqm && <span>📐 {p.sqm.toFixed(0)} sqm</span>}
          {p.floor && <span>🏢 floor {p.floor}</span>}
          {p.notes && <span title={p.notes}>📝 notes</span>}
        </div>
      </div>
    </article>
  );
}
