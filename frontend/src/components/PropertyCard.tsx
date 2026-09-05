import { useState } from "react";
import { formatNumber, useT } from "../i18n";
import { formatPrice } from "../services/api";
import { COMMUTE_ICONS, formatDistance, formatDuration, humanizeFloor } from "../utils/format";
import { PortalBadge } from "./PortalBadge";
import TagPicker from "./TagPicker";
import type { Property, Tag } from "../types";
import {
  Area,
  Atlas,
  Close,
  Deal,
  Email,
  Favorite,
  Filtered,
  Floor,
  Gone,
  Merged,
  NoImage,
  Notes,
  Place,
  PriceDrop,
  Rooms,
  Sold,
  Ticked,
  Unticked,
} from "../ui/icons";

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

/** Travel time from this property to each of the user's saved places.
 *
 *  Absent rather than empty when nothing has been routed yet: the annotation is
 *  cache-only (the grid must never spend a routing request), so a card shows a
 *  commute once the batch in Settings has covered it, and simply says nothing
 *  until then. `detailed` adds the distance, which the modal has room for and
 *  the card does not.
 */
export function CommuteChips(
  { property: p, detailed }: { property: Property; detailed?: boolean },
) {
  const t = useT();
  if (!p.commutes?.length) return null;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs t-body">
      {p.commutes.map((c) => {
        const Mode = COMMUTE_ICONS[c.mode];
        return (
          <span key={`${c.name}-${c.mode}`} className="inline-flex items-center gap-1"
            title={t("card.commuteTitle", { name: c.name })}>
            <Mode /> {c.name} {formatDuration(c.duration_s)}
            {detailed && ` · ${formatDistance(c.distance_m)}`}
          </span>
        );
      })}
    </div>
  );
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
      className={`text-2xs font-semibold px-2 py-0.5 rounded-lg ${
        below ? "chip-positive" : "chip-caution"
      }`}
      title={t("card.medianIn", {
        scope,
        value: formatNumber(Math.round(p.area_median_sqm_price ?? 0)),
      })}>
      {t(below ? "card.belowAverage" : "card.aboveAverage", { pct, scope })}
    </span>
  );
}

/** The "92% match" badge: compatibility with the user's "dream home" settings.
 *  Only rendered when the Smart Match Score feature is on (score is non-null).
 *  Colour tracks the score so a strong match reads at a glance. */
export function MatchBadge({ score }: { score: number | null }) {
  const t = useT();
  if (score === null || score === undefined) return null;
  const chip = score >= 80 ? "chip-positive" : score >= 50 ? "chip-caution" : "chip-neutral";
  return (
    <span className={`inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5
      rounded-lg ${chip}`}
      title={t("card.matchBadgeTitle")}>
      <Deal /> {t("card.matchBadge", { score })}
    </span>
  );
}

/** The "16% below market" badge from the Deal Score. Shown only when the
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
      className={`inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5
        rounded-lg ${under ? "chip-positive" : "chip-caution"}`}
      title={(p.deal_reasons ?? []).join(" · ") || t("card.dealScore")}>
      <Deal />{" "}
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
    <article data-action="property.card"
      onClick={onClick}
      // The whole card opens the property on a click, but it is not itself the
      // button: it holds the star, the hide and the select controls, and an
      // element with a widget role that contains other widgets is ambiguous to
      // a screen reader (axe: nested-interactive) — the card and the controls
      // inside it compete for the same activation. The keyboard route is the
      // title button below instead, which announces the listing and opens it.
      aria-label={p.title || t("card.untitled")}
      className={`glass rounded-2xl overflow-hidden cursor-pointer group hover:border-accent-line hover:shadow-e3 transition-all duration-200 hover:-translate-y-0.5 ${
        selected ? "ring-2 ring-accent border-accent" : ""
      }`}>
      {/* A ratio, not a height: the box is the same shape whatever the card is
          wide, and it is reserved before the image arrives. A portal's signed
          image URL expires often enough that the fallback is a normal state
          rather than an edge case, and neither a slow load nor a dead link may
          move the rows below it. */}
      <div className="relative aspect-[4/3] bg-sunken-strong overflow-hidden">
        {p.image_url && !imgBroken ? (
          <img src={p.image_url} alt={p.title} loading="lazy" decoding="async"
            onError={() => setImgBroken(true)}
            className="w-full h-full object-cover group-hover:scale-105 transition duration-300" />
        ) : (
          <div className="w-full h-full flex items-center justify-center
            text-ink-faint">
            {/* Drawn rather than typed, and drawn by the icon set rather than by
                hand: one stroke weight, `currentColor`, and a size this box
                chooses. An emoji here rendered as a different picture on every
                platform and could be given neither. */}
            <NoImage size={48} strokeWidth={1.25} />
          </div>
        )}
        {/* right padding reserves the quick-action corner, which is wider on
            phones where the buttons grow to a thumb-sized target.

            Every badge here is white on an opaque 700-weight fill. The 600
            weights these used to carry read at 3.1–3.7:1 against white, under
            the 4.5:1 the browser suite gates on, and the translucency made it
            worse still: composited over a bright photo the fill lightens and
            the label fades with it, so the contrast depended on the picture
            behind it. */}
        <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 pr-28 sm:pr-24">
          {isNew && (
            <span
              className="text-3xs font-bold uppercase px-2 py-0.5 rounded bg-portal-immobiliare text-on-solid"
              title={t("card.newTitle")}>
              {t("card.new")}
            </span>
          )}
          {portals.map((portal) => (
            <PortalBadge key={portal} portal={portal} variant="overlay" />
          ))}
          {p.contract === "rent" && (
            <span className="inline-flex items-center gap-1 text-3xs font-bold uppercase
              px-2 py-0.5 rounded bg-rent-deep text-on-solid">
              <Sold /> {t("card.rent")}
            </span>
          )}
          {p.listings.length > 1 && (
            <span className="inline-flex items-center gap-1 text-3xs font-bold px-2 py-0.5
              rounded bg-tag text-on-solid">
              <Merged /> {t("card.mergedListings", { count: p.listings.length })}
            </span>
          )}
          {p.source === "email" && (
            <span className="inline-flex items-center gap-1 text-3xs font-bold px-2 py-0.5
              rounded bg-info text-on-solid"
              title={t("card.emailTitle")}>
              <Email /> {t("card.email")}
            </span>
          )}
        </div>

        {/* quick actions: select + star + hide without opening the modal */}
        <div data-action="property.quickActions" className="absolute top-2 right-2 flex gap-1.5"
          onClick={(e) => e.stopPropagation()}>
          {onToggleSelect && (
            <button data-action="property.select"
              type="button"
              className={`w-9 h-9 sm:w-7 sm:h-7 rounded-lg backdrop-blur flex items-center justify-center text-sm transition btn-focus ${
                selected
                  ? "bg-accent text-on-solid shadow"
                  : "bg-veil text-ink-faint hover:text-accent"
              }`}
              title={selected ? t("card.deselect") : t("card.selectForBatch")}
              // The tick used to be the state, readable as text. It is a drawing
              // now, so the state has to be announced rather than looked at —
              // which is what a screen reader needed all along.
              aria-pressed={selected}
              onClick={onToggleSelect}>
              {selected ? <Ticked size={16} /> : <Unticked size={16} />}
            </button>
          )}
          <button data-action="property.favorite"
            className={`w-9 h-9 sm:w-7 sm:h-7 rounded-lg backdrop-blur flex items-center
              justify-center text-sm transition btn-focus ${
                p.is_favorite
                  ? "bg-favorite text-on-solid"
                  : "bg-veil text-ink-body hover:bg-favorite-soft hover:text-on-solid"
              }`}
            title={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
            aria-label={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
            onClick={onToggleFavorite}>
            <Favorite size={16} fill={p.is_favorite ? "currentColor" : "none"} />
          </button>
          {p.status !== "hidden" && (
            <button data-action="property.hide"
              className="w-9 h-9 sm:w-7 sm:h-7 rounded-lg bg-veil text-ink-body
                backdrop-blur hover:bg-negative-veil hover:text-on-solid flex
                items-center justify-center text-sm transition btn-focus"
              title={t("card.hideTitle")}
              aria-label={t("card.hideAria")}
              onClick={onQuickHide}>
              <Close size={16} />
            </button>
          )}
        </div>

        <div className="absolute bottom-2 left-2 flex flex-wrap gap-1.5">
          {drop !== null && (
            <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-1
              rounded-lg bg-positive text-on-solid">
              <PriceDrop /> {drop.toFixed(1)}%
            </span>
          )}
          {p.status === "filtered" && (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg
              bg-negative-deep text-on-solid">
              <Filtered /> {t("card.filteredReason", { reason: p.filtered_reason ?? "" })}
            </span>
          )}
          {p.status === "gone" && (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg
              bg-neutral-solid text-on-solid">
              <Gone /> {t("card.noLongerAvailable")}
            </span>
          )}
          {p.status === "sold" && (
            <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-1
              rounded-lg bg-caution text-on-solid">
              <Sold /> {t(p.contract === "rent" ? "card.rentedOut" : "card.sold")}
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
            <span className="text-xs t-muted tnum">
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
        {/* The card's keyboard route into the property. Styled as the heading
            it already was — this is the same target the whole card offers a
            pointer, given to Tab as a control a screen reader can name. */}
        <h3 className="font-medium text-sm mt-1">
          <button data-action="property.open" type="button"
            className="text-left w-full line-clamp-2 min-h-[2.5rem] btn-focus rounded"
            onClick={(e) => {
              e.stopPropagation();
              onClick();
            }}>
            {p.title || t("card.untitled")}
          </button>
        </h3>
        <p className="flex items-center gap-1 text-xs t-muted mt-1">
          <Place className="shrink-0" />
          <span className="truncate">
            {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || t("card.locationUnknown")}
          </span>
        </p>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2 text-xs t-body">
          {p.rooms && (
            <span className="inline-flex items-center gap-1">
              <Rooms /> {t("common.rooms", { count: p.rooms })}
            </span>
          )}
          {p.sqm && (
            <span className="inline-flex items-center gap-1">
              <Area /> {t("common.sqm", { value: p.sqm.toFixed(0) })}
            </span>
          )}
          {p.floor && (
            <span className="inline-flex items-center gap-1">
              <Floor /> {humanizeFloor(p.floor)}
            </span>
          )}
          {p.notes && (
            <span className="inline-flex items-center gap-1" title={p.notes}>
              <Notes /> {t("card.notes")}
            </span>
          )}
          {/* Whether the property is placeable on the map. Called out because a
              zone filter silently drops the un-pinned ones (invariant 19), and
              from the grid there was no way to tell which cards those are. */}
          {(p.latitude === null || p.longitude === null) && (
            <span className="inline-flex items-center gap-1 t-dim" title={t("card.notOnMapTitle")}>
              <Atlas /> {t("card.notOnMap")}
            </span>
          )}
        </div>
        <CommuteChips property={p} />
      </div>
    </article>
  );
}
