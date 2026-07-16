import { useState } from "react";
import { api, formatPrice, safeHref } from "../services/api";
import type { Property } from "../types";
import Calculators from "./Calculators";
import { PortalBadge } from "./PortalBadge";
import { DealBadge, MarketBadge } from "./PropertyCard";

interface Props {
  property: Property;
  onClose: () => void;
  onDeleted: () => void;
  onToggleFavorite: () => void;
  onNotesSaved: (updated: Property) => void;
}

export default function PropertyModal({
  property: p, onClose, onDeleted, onToggleFavorite, onNotesSaved,
}: Props) {
  const history = [...p.price_history].reverse();
  const [notes, setNotes] = useState(p.notes);
  const [savingNotes, setSavingNotes] = useState(false);
  const [checkingOnline, setCheckingOnline] = useState(false);
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [imgBroken, setImgBroken] = useState(false);
  const notesDirty = notes !== p.notes;

  async function checkIfOnline() {
    setCheckingOnline(true);
    setCheckResult(null);
    setError("");
    try {
      const { property: updated, summary } = await api.checkSingleProperty(p.id);
      onNotesSaved(updated);
      if (summary.gone > 0) {
        setCheckResult("🔴 Removed / Gone (404)");
      } else if (summary.online > 0) {
        setCheckResult("🟢 Online (just verified)");
      } else {
        setCheckResult("⚠️ Could not verify (blocked by the portal or timeout)");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error during the online check");
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
      setError(e instanceof Error ? e.message : "Could not save notes");
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
                    🔑 rent
                  </span>
                )}
                {p.title || "Untitled"}
              </h2>
              <p className="text-sm t-muted mt-1">
                📍 {[p.city, p.zone, p.address].filter(Boolean).join(" · ") || "N/A"}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                className={`btn-ghost ${p.is_favorite ? "text-yellow-500 dark:text-yellow-400" : ""}`}
                title={p.is_favorite ? "Remove from favorites" : "Add to favorites"}
                aria-label={p.is_favorite ? "Remove from favorites" : "Add to favorites"}
                onClick={onToggleFavorite}>
                {p.is_favorite ? "★" : "☆"}
              </button>
              <button className="btn-ghost" aria-label="Close" onClick={onClose}>✕</button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4 mt-4 text-sm">
            <span className="text-2xl font-bold accent-price">
              {formatPrice(p.current_min_price, p.contract)}
            </span>
            {p.sqm && p.current_min_price && (
              <span className="self-end t-muted">
                {Math.round(p.current_min_price / p.sqm).toLocaleString("en-IE")} €/sqm
              </span>
            )}
            {p.rooms && <span className="self-end">🚪 {p.rooms} rooms</span>}
            {p.sqm && <span className="self-end">📐 {p.sqm.toFixed(0)} sqm</span>}
            <DealBadge property={p} />
            <MarketBadge property={p} />
          </div>

          {/* Deal Score breakdown */}
          {p.deal_score !== null && p.deal_label !== "fair" && (
            <div className="mt-4 rounded-xl panel p-3 text-sm">
              <p className="font-medium mb-1">
                🎯 Deal Score:{" "}
                <span className={p.deal_score > 0 ? "accent-good" : "accent-bad"}>
                  {p.deal_score > 0 ? "+" : ""}{p.deal_score}%
                </span>{" "}
                <span className="t-muted">
                  ({p.deal_label === "undervalued"
                    ? "below the local market"
                    : "above the local market"})
                </span>
              </p>
              {p.deal_reasons && p.deal_reasons.length > 0 && (
                <ul className="list-disc list-inside t-body text-xs space-y-0.5">
                  {p.deal_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {p.target_price_low && p.target_price_high && (
                <p className="mt-2 t-body">
                  💬 Suggested proposal:{" "}
                  <span className="font-semibold">
                    {formatPrice(p.target_price_low, p.contract)} –{" "}
                    {formatPrice(p.target_price_high, p.contract)}
                  </span>
                </p>
              )}
              <p className="mt-2 text-[11px] t-dim">
                An estimate from the area's median €/sqm, the listing's condition
                cues, and the agency's usual discount — a starting point for your
                own judgement, not an appraisal.
              </p>
            </div>
          )}

          {/* Listings merged across portals */}
          <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
            Found listings ({p.listings.length})
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
                <span className="accent-link text-sm shrink-0">Open ↗</span>
              </a>
            ))}
          </div>

          {/* Price history */}
          {history.length > 0 && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                Price history
              </h3>
              <ul className="space-y-1 text-sm">
                {history.map((h, i) => {
                  const pct = h.old_price
                    ? ((h.new_price - h.old_price) / h.old_price) * 100
                    : 0;
                  return (
                    <li key={i} className="flex flex-wrap items-center gap-x-3">
                      <span className="text-xs t-dim w-24">
                        {new Date(h.changed_at).toLocaleDateString("en-IE")}
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

          {/* Personal notes: user-curated, scans never touch them */}
          <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
            📝 Personal notes
          </h3>
          <textarea
            className="input w-full h-24 resize-none"
            placeholder='e.g. "called agent on Monday — viewing scheduled for Friday", "needs 15k renovation"'
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          {notesDirty && (
            <div className="flex justify-end mt-2">
              <button className="btn-primary" onClick={saveNotes} disabled={savingNotes}>
                {savingNotes ? "Saving…" : "Save notes"}
              </button>
            </div>
          )}

          {/* Financial calculators (sale properties only) */}
          <Calculators property={p} />

          {/* Description */}
          {p.listings.some((l) => l.description) && (
            <>
              <h3 className="font-semibold mt-6 mb-2 text-sm uppercase t-muted">
                Description
              </h3>
              <p className="text-sm t-body whitespace-pre-line max-h-48 overflow-y-auto">
                {p.listings.find((l) => l.description)?.description}
              </p>
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
                title="Probes the portal URL right now to verify if this listing is still online or removed (404)">
                {checkingOnline ? "⏳ Checking…" : "🔎 Check if still online"}
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
                  const msg = p.status === "gone"
                    ? "Restore this property? Use this if the availability check marked it \"no longer available\" by mistake."
                    : p.status === "sold"
                    ? "Restore this property? Use this if you marked it sold by mistake — it goes back to active lists."
                    : "Restore this property? It will appear in active lists again.";
                  if (confirm(msg)) {
                    try {
                      await api.restoreProperty(p.id);
                      onDeleted(); // refresh the parent state
                    } catch (e) {
                      setError(e instanceof Error ? e.message : "Restore failed");
                    }
                  }
                }}>
                👁 Restore property
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
                    const label = p.contract === "rent" ? "rented out" : "sold";
                    if (confirm(`Mark this property as ${label}? It leaves the active lists but is kept as a confirmed sale for market statistics.`)) {
                      try {
                        await api.markPropertySold(p.id);
                        onDeleted();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Mark sold failed");
                      }
                    }
                  }}>
                  🔑 Mark {p.contract === "rent" ? "rented" : "sold"}
                </button>
                <button
                  className="accent-bad hover:opacity-80 text-sm transition"
                  onClick={async () => {
                    // the backend marks as "hidden" rather than physical deletion so
                    // subsequent scans do not re-insert or notify it as new
                    if (confirm("Hide this property? It will never appear in lists or notifications again.")) {
                      try {
                        await api.deleteProperty(p.id);
                        onDeleted();
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Hide failed");
                      }
                    }
                  }}>
                  🙈 Hide property
                </button>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
