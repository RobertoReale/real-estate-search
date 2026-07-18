/** Root application dashboard component orchestrating global layout and state.
 *  Manages live property listings, search filters, view modes (Grid / Map),
 *  search profile diagnostics, email import pipelines, and modal dialogues.
 *  Uses a monotonic sequence ref (`refreshSeq`) to prevent race conditions during rapid filter keystrokes. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useProgressPoll } from "./hooks/useProgressPoll";
import EmailImport from "./components/EmailImport";
import FiltersBar from "./components/FiltersBar";
import MapView from "./components/MapView";
import MarketVelocityPanel from "./components/MarketVelocity";
import LogViewer from "./components/LogViewer";
import Navbar from "./components/Navbar";
import PriceTrends from "./components/PriceTrends";
import { ProgressBar } from "./components/ProgressBar";
import PropertyCard from "./components/PropertyCard";
import PropertyModal from "./components/PropertyModal";
import SearchProfiles from "./components/SearchProfiles";
import SettingsModal from "./components/SettingsModal";
import { api } from "./services/api";
import type {
  ImportCheckProgress, ImportCheckSummary, Property, PropertyFilters,
  ScanStatus, SearchProfile, Settings, Tag, ViewMode,
} from "./types";

const DEFAULT_FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "", zone: "", q: "", source: "",
  profile_id: "", tag: "", min_price: "", max_price: "", min_sqm: "",
  max_sqm: "", floor_band: "", rooms: "",
  portal: "", agency: "", deal: "", min_sqm_price: "", max_sqm_price: "",
  merged_only: false,
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: false, sort: "newest",
};

export default function App() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [filters, setFilters] = useState<PropertyFilters>(DEFAULT_FILTERS);
  const [view, setView] = useState<ViewMode>("grid");
  // set by a card's "View on map" jump so MapView centers on that property;
  // cleared on any manual view switch so the map fits the whole set again
  const [mapFocusId, setMapFocusId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Property | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [checkingBatch, setCheckingBatch] = useState(false);
  const [cancellingBatch, setCancellingBatch] = useState(false);
  const [batchProgress, setBatchProgress] = useState<ImportCheckProgress | null>(null);
  const [batchSummary, setBatchSummary] = useState<ImportCheckSummary | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  // monotonic id per refresh: typing in a filter fires overlapping requests,
  // and without this guard a slow older response would land after the newer
  // one and overwrite the grid with stale results
  const refreshSeq = useRef(0);

  // "New" badge threshold: properties first seen after this instant are
  // flagged as new for the rest of this browser session, even if a scan
  // completes while the dashboard stays open. Captured once via a lazy
  // initializer (not an effect) so the very first render already has it —
  // an effect would flash the grid without badges for one frame. The stored
  // timestamp is advanced immediately so a reload (the next time the user
  // "sees" the dashboard, per-device like the theme/token in localStorage)
  // stops flagging today's properties as new. No stored value at all means
  // first-ever run: nothing is flagged, so the whole existing dashboard
  // doesn't light up as "new".
  const [newSinceThreshold] = useState<string | null>(() => {
    const stored = localStorage.getItem("propertiesSeenBefore");
    localStorage.setItem("propertiesSeenBefore", new Date().toISOString());
    return stored;
  });

  const refresh = useCallback(async () => {
    const seq = ++refreshSeq.current;
    try {
      const [props, profs, status, sett, tagList] = await Promise.all([
        api.getProperties(filters),
        api.getProfiles(),
        api.getScanStatus(),
        api.getSettings(),
        api.getTags(),
      ]);
      if (seq !== refreshSeq.current) return; // a newer refresh superseded this one
      setProperties(props);
      setTags(tagList);
      setSelectedIds((prev) => {
        if (prev.size === 0) return prev;
        const validIds = new Set<number>();
        for (const id of prev) {
          if (props.some((p) => p.id === id)) validIds.add(id);
        }
        return validIds;
      });
      setProfiles(profs);
      setScanStatus(status);
      setSettings(sett);
      setLoadError("");
      // keep the open modal in sync with fresh data (e.g. after saving
      // notes or toggling favorite); if the property left the current
      // filter set, keep showing the stale copy until the user closes it
      setSelected((prev) =>
        prev ? props.find((p) => p.id === prev.id) ?? prev : prev
      );
    } catch (e) {
      if (seq !== refreshSeq.current) return;
      setLoadError(
        "Backend unreachable on http://localhost:8000 — start it with start.bat"
      );
    }
  }, [filters]);

  // small debounce: `refresh` changes on every keystroke in the City/price
  // filters, and firing four API calls per letter typed is pure waste
  useEffect(() => {
    const t = window.setTimeout(refresh, 250);
    return () => window.clearTimeout(t);
  }, [refresh]);

  // polling: frequent during scan, slow otherwise
  useEffect(() => {
    const ms = scanStatus?.running ? 4000 : 30000;
    const t = window.setInterval(refresh, ms);
    return () => window.clearInterval(t);
  }, [refresh, scanStatus?.running]);

  // a failed click must say so: without this wrapper the rejection is
  // unhandled and the button silently does nothing, which reads as "broken"
  async function runAction(fn: () => Promise<void>) {
    try {
      setActionError("");
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Action failed");
    }
  }

  // "Find coordinates" from the map's zone-filter banner: the batch geocoder
  // backfills pins for the properties a geographic filter would otherwise drop.
  const [geocoding, setGeocoding] = useState(false);
  function findCoordinates() {
    if (geocoding) return;
    return runAction(async () => {
      setGeocoding(true);
      try {
        await api.geocodeMissing();
      } finally {
        setGeocoding(false);
      }
      await refresh();
    });
  }

  function scanNow() {
    return runAction(async () => {
      await api.triggerScan();
      setScanStatus((s) => (s ? { ...s, running: true } : s));
      setTimeout(refresh, 1500);
    });
  }

  function quickHide(p: Property) {
    // same confirm() used by the modal's "Hide property" action: hiding is
    // irreversible on its own (only a manual "Restore" brings it back), so
    // both entry points must ask the same way
    if (!confirm("Hide this property? It will never appear in lists or notifications again.")) {
      return;
    }
    return runAction(async () => {
      await api.deleteProperty(p.id);
      setProperties((list) => list.filter((x) => x.id !== p.id));
      if (selected?.id === p.id) setSelected(null);
    });
  }

  function toggleFavorite(p: Property) {
    return runAction(async () => {
      const updated = await api.updateProperty(p.id, { is_favorite: !p.is_favorite });
      setProperties((list) => list.map((x) => (x.id === p.id ? updated : x)));
      setSelected((prev) => (prev?.id === p.id ? updated : prev));
    });
  }

  function addTag(p: Property, name: string) {
    return runAction(async () => {
      // idempotent: reuses a case-insensitive match instead of creating a
      // near-duplicate, so the client never needs to pre-check existence
      const tag = await api.createTag(name);
      setTags((list) => (list.some((t) => t.id === tag.id) ? list : [...list, tag]));
      const tagIds = [...new Set([...p.tags.map((t) => t.id), tag.id])];
      const updated = await api.updateProperty(p.id, { tag_ids: tagIds });
      setProperties((list) => list.map((x) => (x.id === p.id ? updated : x)));
      setSelected((prev) => (prev?.id === p.id ? updated : prev));
    });
  }

  function removeTag(p: Property, tagId: number) {
    return runAction(async () => {
      const tagIds = p.tags.map((t) => t.id).filter((id) => id !== tagId);
      const updated = await api.updateProperty(p.id, { tag_ids: tagIds });
      setProperties((list) => list.map((x) => (x.id === p.id ? updated : x)));
      setSelected((prev) => (prev?.id === p.id ? updated : prev));
    });
  }

  // "View on map" from a card: focus the map on this property and switch view.
  // The property is already in the current grid, so it is on the map too (the
  // modal geocodes it first when it had no pin, updating the shared state).
  function showOnMap(p: Property) {
    setMapFocusId(p.id);
    setView("map");
    setSelected(null);
  }

  // Any manual view switch drops the "View on map" focus, so the map goes back
  // to fitting the whole filtered set instead of staying zoomed on one pin.
  function changeView(v: ViewMode) {
    setMapFocusId(null);
    setView(v);
  }

  useProgressPoll(
    checkingBatch,
    api.propertiesCheckProgress,
    (prog) => {
      if (prog.active) setBatchProgress(prog);
    },
    800,
  );

  function bulkAction(action: "hide" | "favorite" | "unfavorite" | "sold") {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (action === "hide" && !confirm(
      `Hide ${ids.length} properties? They will disappear from lists and ` +
      `notifications (recoverable from 🙈 Discarded → Restore).`
    )) return;
    if (action === "sold" && !confirm(
      `Mark ${ids.length} properties as sold/rented out? They leave the active ` +
      `lists but are kept as confirmed sales for the market statistics ` +
      `(recoverable from 🔑 Sold → Restore).`
    )) return;
    return runAction(async () => {
      await api.bulkProperties(ids, action);
      setSelectedIds(new Set());
      setSelectionMode(false);
      await refresh();
    });
  }

  async function checkSelectedProperties() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    setCheckingBatch(true);
    setCancellingBatch(false);
    setBatchSummary(null);
    setBatchProgress(null);
    setActionError("");
    try {
      const summary = await api.checkProperties(ids);
      setBatchSummary(summary);
      await refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Batch check failed");
    } finally {
      setCheckingBatch(false);
      setCancellingBatch(false);
      setBatchProgress(null);
    }
  }

  // The running batch owns the portal connection on its own thread, so this
  // can only ask it to stop after the property currently in flight -- there
  // is no way to cancel a live socket call from here. `cancellingBatch` just
  // disables the button so a second click can't fire a redundant request
  // while the batch (still `checkingBatch`) winds down.
  function stopCheckingProperties() {
    setCancellingBatch(true);
    api.cancelPropertiesCheck().catch(() => {
      // best-effort: if this request itself fails, the batch simply keeps
      // running to completion, same as if the button had never been clicked
    });
  }

  const hasProfiles = profiles.length > 0;


  return (
    <div className="min-h-screen">
      <Navbar
        scanStatus={scanStatus}
        onScanNow={scanNow}
        onOpenSettings={() => setShowSettings(true)}
        onOpenLogs={() => setShowLogs(true)}
      />

      <main className="max-w-7xl mx-auto p-3 sm:p-6 space-y-4 sm:space-y-6">
        {loadError && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm">
            ⚠️ {loadError}
          </div>
        )}
        {actionError && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm flex items-center justify-between gap-3">
            <span>⚠️ {actionError}</span>
            <button className="btn-ghost shrink-0" aria-label="Dismiss error"
              onClick={() => setActionError("")}>✕</button>
          </div>
        )}

        <SearchProfiles profiles={profiles} settings={settings} onChanged={refresh} />

        <EmailImport profiles={profiles} settings={settings} onChanged={refresh} />

        {hasProfiles && (
          <MarketVelocityPanel contract={filters.contract} city={filters.city} />
        )}

        {hasProfiles && (
          <PriceTrends contract={filters.contract} city={filters.city}
            onOpenProperty={setSelected} />
        )}

        <FiltersBar filters={filters} onChange={setFilters} count={properties.length}
          view={view} onViewChange={changeView} profiles={profiles} tags={tags}
          matchEnabled={settings?.match_score_enabled ?? false}
          onReset={() => setFilters({ ...DEFAULT_FILTERS, contract: filters.contract })} />

        {properties.length === 0 && !loadError && (
          <div className="glass rounded-2xl p-6 sm:p-10 text-center t-muted">
            <p className="text-4xl mb-3">🏘️</p>
            <p className="font-medium t-strong">
              {hasProfiles
                ? "No properties match the current filters."
                : "Welcome! Three steps to get started:"}
            </p>
            {!hasProfiles && (
              <ol className="mt-4 text-sm text-left max-w-md mx-auto space-y-2">
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">1</span>
                  <span>
                    Add a search above — describe it in words with "💬 Just
                    describe it", build one with "🧭 Build a search", or paste a
                    results URL from Immobiliare.it / Idealista.{" "}
                    <strong>Tip:</strong> to use every portal filter (bathrooms,
                    floor, elevator, energy class, exclude auctions…), set them
                    on the portal and use "🔗 Paste a URL" — the app monitors
                    exactly that search.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">2</span>
                  Press "▶ Start Scan Now" — the first scan builds your
                  baseline (no notification flood).
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">3</span>
                  Optional: open ⚙️ Settings to enable Telegram or Email
                  alerts for new listings and price drops.
                </li>
              </ol>
            )}
            {hasProfiles && (
              <p className="text-sm mt-1">
                Try switching the Buy/Rent toggle or relaxing the filters.
              </p>
            )}
          </div>
        )}

        {/* Batch Selection & Live Availability Check Bar */}
        {properties.length > 0 && (
          <div className="glass rounded-2xl p-3 sm:p-4 flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={`btn-ghost text-xs px-3 py-1.5 rounded-lg border transition ${
                    selectionMode
                      ? "bg-blue-600 text-white border-blue-600 shadow"
                      : "border-slate-200 dark:border-slate-700 hover:border-blue-500"
                  }`}
                  onClick={() => {
                    setSelectionMode(!selectionMode);
                    if (selectionMode) setSelectedIds(new Set());
                  }}>
                  {selectionMode ? "✕ Close multi-select" : "☐ Select multiple properties"}
                </button>
                {selectionMode && (
                  <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer ml-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === properties.length && properties.length > 0}
                      onChange={() =>
                        setSelectedIds(
                          selectedIds.size === properties.length
                            ? new Set()
                            : new Set(properties.map((p) => p.id))
                        )
                      }
                    />
                    Select all ({selectedIds.size} of {properties.length})
                  </label>
                )}
              </div>
              {selectionMode && selectedIds.size > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-rose-500 hover:text-rose-600 dark:hover:text-rose-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    title="Hidden properties leave the dashboard for good and never come back on their own, even if a scan finds them again. Use Restore to bring one back."
                    onClick={() => bulkAction("hide")}>
                    🙈 Hide selected ({selectedIds.size})
                  </button>
                  <button
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("sold")}>
                    🔑 Mark sold ({selectedIds.size})
                  </button>
                  <button
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("favorite")}>
                    ⭐ Add to favorites
                  </button>
                  <button
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("unfavorite")}>
                    ❌ Remove from favorites
                  </button>
                  <button
                    type="button"
                    className="accent-good text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={checkSelectedProperties}>
                    {checkingBatch ? "⏳ Checking…" : `🔎 Check online availability (${selectedIds.size})`}
                  </button>
                  {checkingBatch && (
                    <button
                      type="button"
                      className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-rose-500 hover:text-rose-600 dark:hover:text-rose-400 flex items-center gap-1.5"
                      disabled={cancellingBatch}
                      onClick={stopCheckingProperties}>
                      {cancellingBatch ? "⏳ Stopping…" : "⏹ Stop"}
                    </button>
                  )}
                </div>
              )}
            </div>

            {checkingBatch && (
              <ProgressBar
                className="pt-2 border-t border-slate-200/50 dark:border-slate-700/50"
                done={batchProgress?.done ?? 0}
                total={batchProgress?.total ?? 0}
                indeterminate={!batchProgress || batchProgress.total <= 0}>
                {batchProgress
                  ? `Checking listing ${batchProgress.done} of ${batchProgress.total} — ${batchProgress.online ?? 0} online, ${batchProgress.gone} removed/sold${(batchProgress.unknown ?? 0) > 0 ? `, ${batchProgress.unknown} not verifiable` : ""}`
                  : "Starting check…"}{" "}
                A safety pause runs between requests to protect the IP from DataDome blocks.
                {batchProgress?.transport && (
                  <span className="block opacity-75 font-normal">
                    Transport: {batchProgress.transport}
                  </span>
                )}
                {batchProgress?.last_error && (
                  <span className="block opacity-75 font-normal">
                    Last issue from the portal: {batchProgress.last_error}
                  </span>
                )}
              </ProgressBar>
            )}

            {batchSummary && !checkingBatch && (
              <div className="pt-2 border-t border-slate-200/50 dark:border-slate-700/50 text-xs t-muted flex items-center justify-between">
                <div>
                  🔎 Checked: <strong>{batchSummary.checked}</strong> |{" "}
                  <span className="text-rose-600 dark:text-rose-400 font-bold">{batchSummary.gone} removed or sold (moved to Gone)</span> |{" "}
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{batchSummary.online} still online</span>
                  {batchSummary.unknown > 0 && ` (${batchSummary.unknown} not verifiable from the portal)`}
                  {batchSummary.cancelled && (
                    <span className="block">
                      ⏹ Stopped — the rest of the selection was left unchecked. Select it again to resume.
                    </span>
                  )}
                  {batchSummary.aborted && !batchSummary.cancelled && (
                    <span className="block text-amber-600 dark:text-amber-400">
                      ⚠️ The portal blocked the requests: check stopped to protect the IP. Try again later.
                      {batchSummary.transport && batchSummary.transport.includes("forced") && (
                        <span className="block font-normal opacity-90">
                          Ran via {batchSummary.transport}. The browser window setting is on, but a
                          background Windows service has no desktop to show a window on. To solve a
                          CAPTCHA yourself, stop the service and run the app normally (start.bat /
                          serve.bat) for this check.
                        </span>
                      )}
                      {batchSummary.transport && !batchSummary.transport.includes("window") && !batchSummary.transport.includes("forced") && (
                        <span className="block font-normal opacity-90">
                          Ran via {batchSummary.transport}. To solve a CAPTCHA yourself, enable
                          both "Run the check through the browser" and "Show the browser window"
                          in Settings (needs the browser engine installed).
                        </span>
                      )}
                    </span>
                  )}
                  {batchSummary.capped && !batchSummary.aborted && !batchSummary.cancelled && (
                    <span className="block">
                      Per-run request limit reached: run the check again to continue with the rest.
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="btn-ghost text-xs py-0.5 px-2"
                  onClick={() => setBatchSummary(null)}>
                  ✕
                </button>
              </div>
            )}
          </div>
        )}

        {view === "map" ? (
          properties.length > 0 && (
            <MapView
              properties={properties}
              onSelect={setSelected}
              focusId={mapFocusId}
              geo={{
                geo_mode: filters.geo_mode,
                center_lat: filters.center_lat,
                center_lng: filters.center_lng,
                radius_m: filters.radius_m,
                poly: filters.poly,
              }}
              onGeoChange={(next) => setFilters((f) => ({ ...f, ...next }))}
              onFindCoordinates={findCoordinates}
              geocoding={geocoding}
            />
          )
        ) : (
          <div className="grid gap-4 sm:gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {properties.map((p) => (
              <PropertyCard
                key={p.id}
                property={p}
                isNew={newSinceThreshold !== null && p.first_seen_at > newSinceThreshold}
                selected={selectedIds.has(p.id)}
                onToggleSelect={
                  selectionMode
                    ? () =>
                        setSelectedIds((prev) => {
                          const n = new Set(prev);
                          if (n.has(p.id)) n.delete(p.id);
                          else n.add(p.id);
                          return n;
                        })
                    : undefined
                }
                onClick={() => {
                  if (selectionMode) {
                    setSelectedIds((prev) => {
                      const n = new Set(prev);
                      if (n.has(p.id)) n.delete(p.id);
                      else n.add(p.id);
                      return n;
                    });
                  } else {
                    setSelected(p);
                  }
                }}
                onQuickHide={() => quickHide(p)}
                onToggleFavorite={() => toggleFavorite(p)}
                allTags={tags}
                onAddTag={(name) => addTag(p, name)}
                onRemoveTag={(tagId) => removeTag(p, tagId)}
              />
            ))}
          </div>
        )}
      </main>

      {selected && (
        <PropertyModal
          property={selected}
          onClose={() => setSelected(null)}
          onDeleted={() => {
            setSelected(null);
            refresh();
          }}
          onToggleFavorite={() => toggleFavorite(selected)}
          onNotesSaved={(updated) => {
            setProperties((list) =>
              list.map((x) => (x.id === updated.id ? updated : x))
            );
            setSelected(updated);
          }}
          onShowOnMap={showOnMap}
          allTags={tags}
          onAddTag={(name) => addTag(selected, name)}
          onRemoveTag={(tagId) => removeTag(selected, tagId)}
        />
      )}
      {showSettings && (
        <SettingsModal
          onClose={() => {
            setShowSettings(false);
            refresh(); // channel warnings depend on the freshly saved settings
          }}
        />
      )}
      {showLogs && <LogViewer onClose={() => setShowLogs(false)} />}
    </div>
  );
}
