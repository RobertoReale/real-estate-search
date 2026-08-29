import { useEffect, useState } from "react";
import { formatDate, formatNumber, useT } from "../i18n";
import { api, formatPrice, safeHref } from "../services/api";
import type { ListingAudit, Property, Tag } from "../types";
import Calculators from "./Calculators";
import { PortalBadge } from "./PortalBadge";
import { CommuteChips, DealBadge, MarketBadge } from "./PropertyCard";
import TagPicker from "./TagPicker";
import { formatSemester } from "../utils/format";

/** The auditor answers inside a fixed vocabulary (backend `listing_auditor`),
 *  so each value has a translation rather than being printed raw. */
const CONDITION_KEYS = {
  new: "audit.conditionNew",
  renovated: "audit.conditionRenovated",
  good: "audit.conditionGood",
  to_renovate: "audit.conditionToRenovate",
  unknown: "audit.conditionUnknown",
} as const;

const TENANT_KEYS = {
  yes: "audit.tenantYes",
  no: "audit.tenantNo",
  unknown: "audit.tenantUnknown",
} as const;

/** One group of the audit's findings; absent entirely when the ad said nothing
 *  about it, since an empty heading reads as a missing answer. */
function AuditList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-xs font-medium">{title}</p>
      <ul className="list-disc list-inside t-body text-xs space-y-0.5">
        {items.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    </div>
  );
}

/** The two price references, side by side and each labelled with what it is.
 *
 *  They are not the same measurement and must never be shown as if they were:
 *  the median is the middle of what comparable **ads ask**, the OMI band is
 *  min/max €/sqm the Agenzia delle Entrate derives from **recorded
 *  transactions**, and asking prices sit systematically above transacted ones.
 *  Averaging them, or letting one stand in for the other, would produce a
 *  number that means nothing and looks authoritative (invariant 22) — so each
 *  column says whose figure it is, the OMI one carries the semester it was
 *  recorded in, and neither is ever rendered bare.
 *
 *  A property with no OMI data shows the median alone, in a single column: an
 *  empty second box would read as a figure that failed to load. With neither,
 *  the panel is absent entirely. */
function PriceBenchmarks({ property: p }: { property: Property }) {
  const t = useT();
  const median = p.area_median_sqm_price;
  const omi = p.omi_min_sqm_price && p.omi_max_sqm_price && p.omi_semester
    ? { min: p.omi_min_sqm_price, max: p.omi_max_sqm_price, semester: p.omi_semester }
    : null;
  if (!median && !omi) return null;
  const scope = t(p.area_median_scope === "zone" ? "card.scopeZone" : "card.scopeCity");
  return (
    <div className="mt-4 rounded-xl panel p-3 text-sm">
      <p className="font-medium mb-2">{t("benchmark.title")}</p>
      <div className={`grid gap-3 ${median && omi ? "sm:grid-cols-2" : "grid-cols-1"}`}>
        {median && (
          <div>
            <p className="text-xs t-muted">{t("benchmark.askingLabel")}</p>
            <p className="font-semibold">
              {t("common.sqmPrice", { value: formatNumber(Math.round(median)) })}
            </p>
            <p className="text-[11px] t-dim">{t("benchmark.askingScope", { scope })}</p>
          </div>
        )}
        {omi && (
          <div>
            <p className="text-xs t-muted">
              {t(p.contract === "rent" ? "benchmark.omiRentLabel" : "benchmark.omiSaleLabel")}
            </p>
            <p className="font-semibold">
              {t(p.contract === "rent" ? "benchmark.rangeMonthly" : "benchmark.range", {
                min: formatNumber(Math.round(omi.min)),
                max: formatNumber(Math.round(omi.max)),
              })}
            </p>
            <p className="text-[11px] t-dim">
              {t("benchmark.omiSource", {
                zone: p.omi_zone_code,
                semester: formatSemester(omi.semester),
              })}
            </p>
          </div>
        )}
      </div>
      {median && omi && <p className="mt-2 text-[11px] t-dim">{t("benchmark.note")}</p>}
    </div>
  );
}

interface Props {
  property: Property;
  onClose: () => void;
  onDeleted: () => void;
  onToggleFavorite: () => void;
  onNotesSaved: (updated: Property) => void;
  onShowOnMap: (property: Property) => void;
  allTags: Tag[];
  onAddTag: (name: string) => void;
  onRemoveTag: (tagId: number) => void;
  /** Whether the optional listing auditor is switched on in Settings. Off is
   *  the default, and then nothing here mentions it — a button for a feature
   *  that would answer "turn it on first" is not a feature. */
  auditEnabled: boolean;
}

export default function PropertyModal({
  property: p, onClose, onDeleted, onToggleFavorite, onNotesSaved, onShowOnMap,
  allTags, onAddTag, onRemoveTag, auditEnabled,
}: Props) {
  const t = useT();
  const history = [...p.price_history].reverse();
  const [notes, setNotes] = useState(p.notes);
  const [savingNotes, setSavingNotes] = useState(false);
  const [checkingOnline, setCheckingOnline] = useState(false);
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const [imgBroken, setImgBroken] = useState(false);
  const [audit, setAudit] = useState<ListingAudit | null>(null);
  const [auditing, setAuditing] = useState(false);
  const notesDirty = notes !== p.notes;
  const hasCoords = p.latitude !== null && p.longitude !== null;
  const hasDescription = p.listings.some((l) => l.description);

  // A reading already paid for shows up on its own; producing one never does.
  // The GET reads the stored row and nothing else, so opening a card cannot
  // spend a model request — same split as the commute annotation.
  useEffect(() => {
    if (!auditEnabled) return;
    let cancelled = false;
    api.getPropertyAudit(p.id)
      .then((stored) => { if (!cancelled) setAudit(stored); })
      .catch(() => { /* nothing stored is the common case, not an error */ });
    return () => { cancelled = true; };
  }, [p.id, auditEnabled]);

  async function readListing(force = false) {
    setAuditing(true);
    setError("");
    try {
      setAudit(await api.auditProperty(p.id, force));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("audit.failed"));
    } finally {
      setAuditing(false);
    }
  }

  async function viewOnMap() {
    // Already placed: jump straight to the pin.
    if (hasCoords) {
      onShowOnMap(p);
      return;
    }
    // No coordinates yet — resolve them on demand (portals omit them ~70% of
    // the time), then show the map. Fail-open: an address too vague to place
    // is not an error, it just leaves the property off the map.
    setLocating(true);
    setError("");
    try {
      const { property: updated, located } = await api.geocodeProperty(p.id);
      onNotesSaved(updated); // updated coords flow into the grid + map state
      if (located) {
        onShowOnMap(updated);
      } else {
        setError(t("modal.locateFailed"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("modal.locateError"));
    } finally {
      setLocating(false);
    }
  }

  async function checkIfOnline() {
    setCheckingOnline(true);
    setCheckResult(null);
    setError("");
    try {
      const { property: updated, summary } = await api.checkSingleProperty(p.id);
      onNotesSaved(updated);
      if (summary.gone > 0) {
        setCheckResult(t("modal.checkGone"));
      } else if (summary.online > 0) {
        setCheckResult(t("modal.checkOnline"));
      } else {
        setCheckResult(t("modal.checkUnknown"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("modal.checkError"));
    } finally {
      setCheckingOnline(false);
    }
  }

  async function saveNotes() {
    setSavingNotes(true);
    try {
      const updated = await api.updateProperty(p.id, { notes });
      onNotesSaved(updated);
      setError("");
    } catch (e) {
      // the unsaved text stays in the textarea, so a retry costs one click
      setError(e instanceof Error ? e.message : t("modal.notesError"));
    } finally {
      setSavingNotes(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      {/* dvh, not vh: a mobile browser's `vh` ignores the collapsing address
          bar, so the modal would be taller than the visible viewport and its
          last row (Hide/Restore) would sit under the chrome, unreachable. */}
      <div className="glass rounded-2xl max-w-2xl w-full max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        {p.image_url && !imgBroken && (
          <img src={p.image_url} alt={p.title} className="w-full h-40 sm:h-56 object-cover"
            onError={() => setImgBroken(true)} />
        )}
        <div className="p-4 sm:p-6">
          <div className="flex items-start justify-between gap-2 sm:gap-4">
            <div className="min-w-0">
              <h2 className="text-lg font-bold">
                {p.contract === "rent" && (
                  <span className="text-[10px] font-bold uppercase align-middle px-2 py-0.5 mr-2 rounded chip-teal">
                    {t("card.rent")}
                  </span>
                )}
                {p.title || t("card.untitled")}
              </h2>
              <p className="text-sm t-muted mt-1">
                📍 {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || t("common.notAvailable")}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                className={`btn-ghost ${p.is_favorite ? "text-yellow-500 dark:text-yellow-400" : ""}`}
                title={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
                aria-label={p.is_favorite ? t("card.removeFavorite") : t("card.addFavorite")}
                onClick={onToggleFavorite}>
                {p.is_favorite ? "★" : "☆"}
              </button>
              <button className="btn-ghost" aria-label={t("common.close")} onClick={onClose}>✕</button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 mt-4 text-sm">
            <span className="text-2xl font-bold accent-price">
              {formatPrice(p.current_min_price, p.contract)}
            </span>
            {p.sqm && p.current_min_price && (
              <span className="self-end t-muted">
                {t("common.sqmPrice", {
                  value: formatNumber(Math.round(p.current_min_price / p.sqm)),
                })}
              </span>
            )}
            {p.rooms && <span className="self-end">🚪 {t("common.rooms", { count: p.rooms })}</span>}
            {p.sqm && <span className="self-end">📐 {t("common.sqm", { value: p.sqm.toFixed(0) })}</span>}
            <DealBadge property={p} />
            <MarketBadge property={p} />
          </div>

          <PriceBenchmarks property={p} />

          {/* Deal Score breakdown */}
          {p.deal_score !== null && p.deal_label !== "fair" && (
            <div className="mt-4 rounded-xl panel p-3 text-sm">
              <p className="font-medium mb-1">
                {t("modal.dealScoreTitle")}{" "}
                <span className={p.deal_score > 0 ? "accent-good" : "accent-bad"}>
                  {p.deal_score > 0 ? "+" : ""}{p.deal_score}%
                </span>{" "}
                <span className="t-muted">
                  ({t(p.deal_label === "undervalued"
                    ? "modal.dealBelowLocal"
                    : "modal.dealAboveLocal")})
                </span>
              </p>
              {p.deal_reasons && p.deal_reasons.length > 0 && (
                <ul className="list-disc list-inside t-body text-xs space-y-0.5">
                  {p.deal_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {p.target_price_low && p.target_price_high && (
                <p className="mt-2 t-body">
                  {t("modal.suggestedProposal")}{" "}
                  <span className="font-semibold">
                    {formatPrice(p.target_price_low, p.contract)} –{" "}
                    {formatPrice(p.target_price_high, p.contract)}
                  </span>
                </p>
              )}
              <p className="mt-2 text-[11px] t-dim">{t("modal.dealDisclaimer")}</p>
            </div>
          )}

          {/* Listings merged across portals */}
          <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
            {t("modal.foundListings", { count: p.listings.length })}
          </h3>
          <div className="space-y-2">
            {p.listings.map((l) => (
              <a key={l.id} href={safeHref(l.url)} target="_blank" rel="noreferrer"
                className="flex items-center gap-3 p-3 rounded-xl panel hover:border-blue-500/50 transition">
                <PortalBadge portal={l.portal} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{formatPrice(l.price, p.contract)}</p>
                  {l.agency && (
                    <p className="text-xs t-dim truncate">🏢 {l.agency}</p>
                  )}
                </div>
                <span className="accent-link text-sm shrink-0">{t("modal.open")}</span>
              </a>
            ))}
          </div>

          {/* Price history */}
          {history.length > 0 && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                {t("modal.priceHistory")}
              </h3>
              <ul className="space-y-1 text-sm">
                {history.map((h, i) => {
                  const pct = h.old_price
                    ? ((h.new_price - h.old_price) / h.old_price) * 100
                    : 0;
                  return (
                    <li key={i} className="flex flex-wrap items-center gap-x-3">
                      <span className="text-xs t-dim w-24">
                        {formatDate(h.changed_at)}
                      </span>
                      <span className="line-through t-dim">
                        {formatPrice(h.old_price)}
                      </span>
                      <span>→ {formatPrice(h.new_price)}</span>
                      <span className={pct < 0 ? "accent-good" : "accent-bad"}>
                        {pct > 0 ? "+" : ""}{pct.toFixed(1)}%
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          {/* Travel time to the user's saved places. Nothing renders until the
              commute batch has routed this pin (the annotation is cache-only). */}
          {p.commutes.length > 0 && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                {t("modal.commute")}
              </h3>
              <CommuteChips property={p} detailed />
            </>
          )}

          {/* Provenance: which monitored searches have found this property.
              Empty for an email import a scan has never re-found (invariant 19/20). */}
          {p.found_by.length > 0 && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                {p.found_by.length > 1
                  ? t("modal.foundBySearches", { count: p.found_by.length })
                  : t("modal.foundBySearch")}
              </h3>
              <div className="flex flex-wrap gap-2">
                {p.found_by.map((s) => (
                  <span key={s.id}
                    className="text-xs px-2.5 py-1 rounded-full panel border border-slate-200 dark:border-slate-700">
                    {s.name}
                  </span>
                ))}
              </div>
            </>
          )}
          {p.found_by.length === 0 && p.source === "email" && (
            <p className="mt-6 text-xs t-dim">{t("modal.notLinked")}</p>
          )}

          {/* Tags: user-curated categories, scans never touch them */}
          <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
            {t("modal.tags")}
          </h3>
          <TagPicker tags={p.tags} allTags={allTags} onAdd={onAddTag} onRemove={onRemoveTag} />

          {/* Personal notes: user-curated, scans never touch them */}
          <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
            {t("modal.notes")}
          </h3>
          <textarea
            className="input w-full h-24 resize-none"
            placeholder={t("modal.notesPlaceholder")}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          {notesDirty && (
            <div className="flex justify-end mt-2">
              <button className="btn-primary" onClick={saveNotes} disabled={savingNotes}>
                {savingNotes ? t("common.saving") : t("modal.saveNotes")}
              </button>
            </div>
          )}

          {/* Financial calculators (sale properties only) */}
          <Calculators property={p} />

          {/* Description */}
          {hasDescription && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                {t("modal.description")}
              </h3>
              <p className="text-sm t-body whitespace-pre-line max-h-48 overflow-y-auto">
                {p.listings.find((l) => l.description)?.description}
              </p>
            </>
          )}

          {/* What the optional model read in that description. Off by default,
              and it only ever runs on the press below — never on opening. */}
          {auditEnabled && hasDescription && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                {t("audit.title")}
              </h3>
              {audit && (
                <div className="rounded-xl panel p-3 text-sm space-y-2">
                  {audit.stale && (
                    <p className="text-xs accent-bad">{t("audit.stale")}</p>
                  )}
                  {audit.summary && <p className="t-body">{audit.summary}</p>}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    <span>
                      <span className="t-dim">{t("audit.condition")}: </span>
                      {t(CONDITION_KEYS[audit.condition])}
                    </span>
                    <span>
                      <span className="t-dim">{t("audit.tenant")}: </span>
                      {t(TENANT_KEYS[audit.tenant])}
                    </span>
                  </div>
                  <AuditList title={t("audit.costs")} items={audit.costs} />
                  <AuditList title={t("audit.concerns")} items={audit.concerns} />
                  <AuditList title={t("audit.negotiation")} items={audit.negotiation} />
                  <p className="text-[11px] t-dim">
                    {t("audit.footer", {
                      model: audit.model,
                      date: formatDate(audit.created_at),
                    })}
                    {" · "}
                    {t("audit.disclaimer")}
                  </p>
                </div>
              )}
              <div className="mt-2">
                <button
                  type="button"
                  className="btn-ghost text-xs border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-lg"
                  disabled={auditing}
                  onClick={() => readListing(audit !== null)}
                  title={t("audit.buttonTitle")}>
                  {auditing
                    ? t("audit.reading")
                    : audit
                      ? t("audit.again")
                      : t("audit.button")}
                </button>
              </div>
            </>
          )}

          {error && (
            <p className="text-sm text-rose-600 dark:text-rose-300 mt-4">⚠️ {error}</p>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 mt-6">
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="btn-ghost text-xs border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-lg flex items-center gap-1.5"
                disabled={checkingOnline || !p.listings.length}
                onClick={checkIfOnline}
                title={t("modal.checkOnlineTitle")}>
                {checkingOnline ? t("app.checking") : t("modal.checkOnlineButton")}
              </button>
              <button
                type="button"
                className="btn-ghost text-xs border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-lg flex items-center gap-1.5"
                disabled={locating}
                onClick={viewOnMap}
                title={t(hasCoords ? "modal.viewOnMapTitle" : "modal.locateAndViewTitle")}>
                {locating ? t("filters.locating") : t("modal.viewOnMap")}
              </button>
              {checkResult && (
                <span className="text-xs font-medium animate-fade-in">
                  {checkResult}
                </span>
              )}
            </div>
            {p.status === "hidden" || p.status === "gone" || p.status === "sold" ? (
              <button
                className="accent-good hover:opacity-80 text-sm transition"
                onClick={async () => {
                  // The availability check fails open (invariant 16), but a
                  // portal redirect or block it misread as removal can still
                  // mark a live listing "gone" — this is the way back for
                  // that case, a manual "Hide", and a mistaken "Mark sold".
                  const msg = t(
                    p.status === "gone"
                      ? "modal.restoreGone"
                      : p.status === "sold"
                        ? "modal.restoreSold"
                        : "modal.restoreHidden",
                  );
                  if (confirm(msg)) {
                    try {
                      await api.restoreProperty(p.id);
                      onDeleted(); // refresh the parent state
                    } catch (e) {
                      setError(e instanceof Error ? e.message : t("modal.restoreFailed"));
                    }
                  }
                }}>
                {t("modal.restore")}
              </button>
            ) : (
              <div className="flex items-center gap-3">
                <button
                  className="text-amber-600 dark:text-amber-400 hover:opacity-80 text-sm transition"
                  onClick={async () => {
                    // "sold" is a confirmed market close: it leaves the grid
                    // like "hidden" but is kept as a real sale date feeding the
                    // market-velocity signals. For the "VENDUTO" re-posts that
                    // stay online for weeks and never leave on their own.
                    const msg = t(
                      p.contract === "rent" ? "modal.confirmRented" : "modal.confirmSold",
                    );
                    if (confirm(msg)) {
                      try {
                        await api.markPropertySold(p.id);
                        onDeleted();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : t("modal.markSoldFailed"));
                      }
                    }
                  }}>
                  {t(p.contract === "rent" ? "modal.markRented" : "modal.markSold")}
                </button>
                <button
                  className="accent-bad hover:opacity-80 text-sm transition"
                  onClick={async () => {
                    // the backend marks as "hidden" rather than physical deletion so
                    // subsequent scans do not re-insert or notify it as new
                    if (confirm(t("app.confirmHideOne"))) {
                      try {
                        await api.deleteProperty(p.id);
                        onDeleted();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : t("modal.hideFailed"));
                      }
                    }
                  }}>
                  {t("modal.hide")}
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
