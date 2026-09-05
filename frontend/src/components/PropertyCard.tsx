/** One property, on a skeleton every other card also has.
 *
 *  The rebuild is the point. The card used to lay itself out from whatever the
 *  listing happened to carry: a badge row that was empty on one card and two
 *  lines on the next, a tag strip that appeared only once something had been
 *  tagged, a commute row that existed only after a routing batch had covered
 *  it. Every one of those pushed the rows under it down, so four cards in a row
 *  had their titles at four heights and their prices at four more, and a reader
 *  scanning the grid had to find each field again on every card instead of
 *  reading down a column.
 *
 *  So the shape is fixed and the content varies inside it. Six zones, in this
 *  order and at these heights whatever the data:
 *
 *      image (4:3) · title · address · price · facts · market · tags
 *
 *  Each carries a `data-zone`, and the browser suite asserts that the tops of
 *  the corresponding zones line up across a row of four. They are `data-zone`
 *  and not `data-action` on purpose: they hold no handler, and the action
 *  inventory is a list of things a user can press.
 *
 *  Three consequences worth naming, because each one is a decision rather than
 *  a detail:
 *
 *  - **The title is above the price.** A card is found by what it is and then
 *    judged by what it costs; the price used to come first and the eye had to
 *    jump back up for the address.
 *  - **The tags are last and appear on hover.** Tagging is editing, and an
 *    editing affordance sitting in the middle of the reading path was read as
 *    part of the listing. It is `opacity`, not `hidden`: the row still occupies
 *    its zone (so nothing moves when it appears) and is still operable by
 *    pointer and by keyboard, which `display: none` would end.
 *  - **One market statement, never two.** See `utils/marketPosition.ts` for the
 *    precedence and for why the OMI band takes no part in it (invariant 22).
 *
 *  Everything that is a *state* of the listing rather than a fact about it —
 *  new, portal, merged, a price drop, gone, sold, no pin, has notes — is an
 *  overlay on the image, where a variable number of them costs no layout at
 *  all.
 */
import { useState } from "react";
import { formatNumber, useT } from "../i18n";
import { formatPrice } from "../services/api";
import { humanizeFloor } from "../utils/format";
import { marketPosition } from "../utils/marketPosition";
import { PortalBadge } from "./PortalBadge";
import TagPicker from "./TagPicker";
import type { Property, Tag } from "../types";
import { Card, Chip } from "../ui";
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

/** Every overlay badge is white on an opaque 700-weight fill. The 600 weights
 *  these used to carry read at 3.1–3.7:1 against white, under the 4.5:1 the
 *  browser suite gates on, and the translucency made it worse still: composited
 *  over a bright photo the fill lightens and the label fades with it, so the
 *  contrast depended on the picture behind it. */
const OVERLAY = "inline-flex items-center gap-1 rounded text-3xs font-bold px-2 py-0.5 text-on-solid";
const MARKER = "inline-flex items-center gap-1 rounded-lg text-xs px-2 py-1 text-on-solid";

/** The dream-home score's fill, which tracks the score so a strong match reads
 *  before the number does. Solid rather than tinted: it sits on a photograph. */
function matchFill(score: number): string {
  if (score >= 80) return "bg-positive";
  if (score >= 50) return "bg-caution";
  return "bg-neutral-solid";
}

/** A fact slot: always rendered, so the three of them are always in the same
 *  places. An em dash is the honest answer to "how many rooms" when the ad did
 *  not say — and it keeps the row the same height as one that did. */
function Fact({ icon, value }: { icon: React.ReactNode; value: string | null }) {
  return (
    <span className={`inline-flex items-center gap-1 ${value === null ? "t-dim" : ""}`}>
      {icon} {value ?? "—"}
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
  const market = marketPosition(p);
  const scope = market?.kind === "median"
    ? t(market.scope === "zone" ? "card.scopeZone" : "card.scopeCity")
    : "";
  // portal image URLs are often signed/expiring CDN links: a stale one fails
  // to load, and the browser's broken-image icon renders the alt text right
  // under the absolutely-positioned badges instead of the placeholder icon
  const [imgBroken, setImgBroken] = useState(false);

  return (
    <Card asChild padding="none"
      className="overflow-hidden cursor-pointer group hover:border-accent-line
        hover:shadow-e3 transition-all duration-200 hover:-translate-y-0.5">
      <article data-action="property.card"
        onClick={onClick}
        // The whole card opens the property on a click, but it is not itself the
        // button: it holds the star, the hide and the select controls, and an
        // element with a widget role that contains other widgets is ambiguous to
        // a screen reader (axe: nested-interactive) — the card and the controls
        // inside it compete for the same activation. The keyboard route is the
        // title button below instead, which announces the listing and opens it.
        aria-label={p.title || t("card.untitled")}
        className={selected ? "ring-2 ring-accent border-accent" : undefined}>
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
              phones where the buttons grow to a thumb-sized target */}
          <div className="absolute top-2 left-2 flex flex-wrap gap-1.5 pr-28 sm:pr-24">
            {isNew && (
              <span className={`${OVERLAY} uppercase bg-portal-immobiliare`}
                title={t("card.newTitle")}>
                {t("card.new")}
              </span>
            )}
            {portals.map((portal) => (
              <PortalBadge key={portal} portal={portal} variant="overlay" />
            ))}
            {p.contract === "rent" && (
              <span className={`${OVERLAY} uppercase bg-rent-deep`}>
                <Sold /> {t("card.rent")}
              </span>
            )}
            {/* The dream-home score. An overlay rather than a row of its own:
                it is a judgement about the listing, and the one row this card
                keeps for judgements is the market line, which says something
                about the price instead. */}
            {p.match_score !== null && p.match_score !== undefined && (
              <span className={`${OVERLAY} ${matchFill(p.match_score)}`}
                title={t("card.matchBadgeTitle")}>
                <Deal /> {t("card.matchBadge", { score: p.match_score })}
              </span>
            )}
            {p.listings.length > 1 && (
              <span className={`${OVERLAY} bg-tag`}>
                <Merged /> {t("card.mergedListings", { count: p.listings.length })}
              </span>
            )}
            {p.source === "email" && (
              <span className={`${OVERLAY} bg-info`} title={t("card.emailTitle")}>
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
              <span className={`${MARKER} font-bold bg-positive`}>
                <PriceDrop /> {drop.toFixed(1)}%
              </span>
            )}
            {p.status === "filtered" && (
              <span className={`${MARKER} bg-negative-deep`}>
                <Filtered /> {t("card.filteredReason", { reason: p.filtered_reason ?? "" })}
              </span>
            )}
            {p.status === "gone" && (
              <span className={`${MARKER} bg-neutral-solid`}>
                <Gone /> {t("card.noLongerAvailable")}
              </span>
            )}
            {p.status === "sold" && (
              <span className={`${MARKER} font-bold bg-caution`}>
                <Sold /> {t(p.contract === "rent" ? "card.rentedOut" : "card.sold")}
              </span>
            )}
            {p.notes && (
              <span className={`${MARKER} bg-neutral-solid`} title={p.notes}>
                <Notes /> {t("card.notes")}
              </span>
            )}
            {/* Whether the property is placeable on the map. Called out because a
                zone filter silently drops the un-pinned ones (invariant 19), and
                from the grid there was no way to tell which cards those are. */}
            {(p.latitude === null || p.longitude === null) && (
              <span className={`${MARKER} bg-neutral-solid`}
                title={t("card.notOnMapTitle")}>
                <Atlas /> {t("card.notOnMap")}
              </span>
            )}
          </div>
        </div>

        <div className="p-4 flex flex-col gap-2">
          {/* The card's keyboard route into the property. Styled as the heading
              it already was — this is the same target the whole card offers a
              pointer, given to Tab as a control a screen reader can name. Two
              lines, always: a one-line title leaves the second line empty
              rather than pulling the price up into it. */}
          <h3 data-zone="title" className="h-10 font-medium text-sm leading-5">
            <button data-action="property.open" type="button"
              className="text-left w-full line-clamp-2 btn-focus rounded"
              onClick={(e) => {
                e.stopPropagation();
                onClick();
              }}>
              {p.title || t("card.untitled")}
            </button>
          </h3>
          <p data-zone="address" className="h-4 flex items-center gap-1 text-xs t-muted">
            <Place className="shrink-0" />
            <span className="truncate">
              {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || t("card.locationUnknown")}
            </span>
          </p>
          <div data-zone="price" className="h-7 flex items-baseline justify-between gap-2">
            <span className="text-xl font-bold accent-price">
              {formatPrice(p.current_min_price, p.contract)}
            </span>
            {sqmPrice && (
              <span className="text-xs t-muted tnum">
                {t("common.sqmPrice", { value: formatNumber(sqmPrice) })}
              </span>
            )}
          </div>
          <div data-zone="facts" className="h-4 flex items-center gap-x-3 text-xs t-body">
            <Fact icon={<Rooms />}
              value={p.rooms ? t("common.rooms", { count: p.rooms }) : null} />
            <Fact icon={<Area />}
              value={p.sqm ? t("common.sqm", { value: p.sqm.toFixed(0) }) : null} />
            <Fact icon={<Floor />} value={p.floor ? humanizeFloor(p.floor) : null} />
          </div>
          {/* Exactly one statement about where this price sits, or none. The row
              is here either way, so a card the backend could not judge is the
              same height as one it could. */}
          <div data-zone="market" className="h-6 flex items-center">
            {market?.kind === "deal" && (
              <span title={market.reasons.join(" · ") || t("card.dealScore")}>
                <Chip tone={market.under ? "positive" : "caution"} className="font-semibold">
                  <Deal />{" "}
                  {t(market.under ? "card.dealBelowMarket" : "card.dealAboveMarket", {
                    pct: market.pct,
                  })}
                </Chip>
              </span>
            )}
            {market?.kind === "median" && (
              <span
                title={t("card.medianIn", {
                  scope,
                  value: formatNumber(Math.round(market.median ?? 0)),
                })}>
                <Chip tone={market.below ? "positive" : "caution"} className="font-semibold">
                  {t(market.below ? "card.belowAverage" : "card.aboveAverage", {
                    pct: market.pct, scope,
                  })}
                </Chip>
              </span>
            )}
          </div>
          {/* Editing, not reading: revealed on hover and on focus, and holding
              its height either way so nothing below it moves. `opacity` rather
              than `hidden` — a control a keyboard can reach must stay a control
              a keyboard can operate. */}
          <div data-zone="tags"
            className="h-7 flex items-center opacity-0 transition-opacity
              group-hover:opacity-100 group-focus-within:opacity-100">
            <TagPicker tags={p.tags} allTags={allTags} onAdd={onAddTag} onRemove={onRemoveTag} compact />
          </div>
        </div>
      </article>
    </Card>
  );
}
