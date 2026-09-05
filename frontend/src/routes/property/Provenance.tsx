/** Where this property came from and what it has done since: the ads behind
 *  it, every price they have carried, how far it is from the places that
 *  matter, and which monitored search found it.
 *
 *  All four are the answer to "why am I looking at this, and can I trust it" —
 *  which is why they sit together rather than being spread through the page.
 */
import { formatDate, useT } from "../../i18n";
import { formatPrice, safeHref } from "../../services/api";
import type { Property } from "../../types";
import { Agency, Commute, External, Searches } from "../../ui/icons";
import { PortalBadge } from "../../components/PortalBadge";
import { COMMUTE_ICONS, formatDistance, formatDuration } from "../../utils/format";

const HEADING = "flex items-center gap-1.5 font-semibold mb-2 text-sm uppercase t-muted";

/** Travel time from this property to each of the user's saved places, with the
 *  distance the card has no room for.
 *
 *  Absent rather than empty when nothing has been routed yet: the annotation is
 *  cache-only (the grid must never spend a routing request), so this appears
 *  once the batch in Settings has covered the property, and simply says nothing
 *  until then. */
function Commutes({ property: p }: { property: Property }) {
  const t = useT();
  if (!p.commutes.length) return null;
  return (
    <section>
      <h3 className={HEADING}><Commute /> {t("detail.commute")}</h3>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs t-body">
        {p.commutes.map((c) => {
          const Mode = COMMUTE_ICONS[c.mode];
          return (
            <span key={`${c.name}-${c.mode}`} className="inline-flex items-center gap-1"
              title={t("card.commuteTitle", { name: c.name })}>
              <Mode /> {c.name} {formatDuration(c.duration_s)}
              {` · ${formatDistance(c.distance_m)}`}
            </span>
          );
        })}
      </div>
    </section>
  );
}

export function Provenance({ property: p }: { property: Property }) {
  const t = useT();
  // Newest first: the last thing that happened to the price is the thing worth
  // reading, and the list is stored the other way round.
  const history = [...p.price_history].reverse();

  return (
    <div className="space-y-6">
      {/* The ads merged into this one property, each a way out to the portal. */}
      <section>
        <h3 className="font-semibold mb-2 text-sm uppercase t-muted">
          {t("detail.foundListings", { count: p.listings.length })}
        </h3>
        <div className="space-y-2">
          {p.listings.map((l) => (
            <a key={l.id} href={safeHref(l.url)} target="_blank" rel="noreferrer"
              className="flex items-center gap-3 p-3 rounded-xl panel hover:border-accent-line transition">
              <PortalBadge portal={l.portal} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium tnum">{formatPrice(l.price, p.contract)}</p>
                {l.agency && (
                  <p className="flex items-center gap-1 text-xs t-dim">
                    <Agency className="shrink-0" />
                    <span className="truncate">{l.agency}</span>
                  </p>
                )}
              </div>
              <span className="inline-flex items-center gap-1 accent-link text-sm shrink-0">
                {t("common.open")} <External />
              </span>
            </a>
          ))}
        </div>
      </section>

      {history.length > 0 && (
        <section>
          <h3 className="font-semibold mb-2 text-sm uppercase t-muted">
            {t("detail.priceHistory")}
          </h3>
          <ul className="space-y-1 text-sm tnum">
            {history.map((h, i) => {
              const pct = h.old_price
                ? ((h.new_price - h.old_price) / h.old_price) * 100
                : 0;
              return (
                <li key={i} className="flex flex-wrap items-center gap-x-3">
                  <span className="text-xs t-dim w-24">{formatDate(h.changed_at)}</span>
                  <span className="line-through t-dim">{formatPrice(h.old_price)}</span>
                  <span>→ {formatPrice(h.new_price)}</span>
                  <span className={pct < 0 ? "accent-good" : "accent-bad"}>
                    {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <Commutes property={p} />

      {/* Which monitored searches have found this property. Empty for an email
          import a scan has never re-found (invariant 19/20). */}
      {p.found_by.length > 0 && (
        <section>
          <h3 className={HEADING}>
            <Searches />{" "}
            {p.found_by.length > 1
              ? t("detail.foundBySearches", { count: p.found_by.length })
              : t("detail.foundBySearch")}
          </h3>
          <div className="flex flex-wrap gap-2">
            {p.found_by.map((s) => (
              <span key={s.id}
                className="text-xs px-2.5 py-1 rounded-full panel border border-line">
                {s.name}
              </span>
            ))}
          </div>
        </section>
      )}
      {p.found_by.length === 0 && p.source === "email" && (
        <p className="text-xs t-dim">{t("detail.notLinked")}</p>
      )}
    </div>
  );
}
