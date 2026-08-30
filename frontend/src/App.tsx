/** Root application dashboard component orchestrating global layout and state.
 *  Manages live property listings, search filters, view modes (Grid / Map),
 *  search profile diagnostics, and modal dialogues.
 *  Uses a monotonic sequence ref (`refreshSeq`) to prevent race conditions during rapid filter keystrokes. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useProgressPoll } from "./hooks/useProgressPoll";
import FiltersBar from "./components/FiltersBar";
import MapView from "./components/MapView";
import MarketVelocityPanel from "./components/MarketVelocity";
import LogViewer from "./components/LogViewer";
import Navbar from "./components/Navbar";
import PriceTrends from "./components/PriceTrends";
import ScraperHealthPanel from "./components/ScraperHealth";
import { ProgressBar } from "./components/ProgressBar";
import PropertyCard from "./components/PropertyCard";
import PropertyModal from "./components/PropertyModal";
import SearchProfiles from "./components/SearchProfiles";
import SettingsModal from "./components/SettingsModal";
import { api } from "./services/api";
import { useT } from "./i18n";
import type {
  AvailabilityCheckProgress, AvailabilityCheckSummary, Property, PropertyFilters,
  ScanStatus, SearchProfile, Settings, Tag, ViewMode,
} from "./types";

/** "New" badge threshold: properties first seen after this instant are flagged
 *  as new for the rest of this browser session, even if a scan completes while
 *  the dashboard stays open. The stored timestamp is advanced immediately so a
 *  reload (the next time the user "sees" the dashboard, per-device like the
 *  theme and the token in localStorage) stops flagging today's properties as
 *  new. No stored value at all means first-ever run: nothing is flagged, so the
 *  whole existing dashboard doesn't light up as "new".
 *
 *  Memoised at module scope, and that is the load-bearing part: this is read
 *  from a `useState` initializer, which StrictMode deliberately invokes twice.
 *  Reading and writing localStorage in there directly meant the second
 *  invocation read back the timestamp the first had just written — so in
 *  development the threshold was always "now" and no card was ever badged,
 *  while the production build (no double invocation) behaved correctly. A
 *  feature that only misbehaves where it is developed is a feature nobody can
 *  verify.
 */
const SEEN_KEY = "propertiesSeenBefore";
let seenBefore: string | null | undefined;

export function readSeenThreshold(): string | null {
  if (seenBefore === undefined) {
    seenBefore = localStorage.getItem(SEEN_KEY);
    localStorage.setItem(SEEN_KEY, new Date().toISOString());
  }
  return seenBefore;
}

/** Drop from the selection the properties that have left the filtered set — but
 *  only when this fetch actually saw all of it.
 *
 *  "Select all" means the whole filtered set and asks the backend for it
 *  (`limit: 0`), while the grid keeps holding one window. Intersecting the
 *  selection against that window on the next refresh — which any scan triggers,
 *  and the poll every 30s — silently turned "hide all 300 results" into "hide
 *  the first 60": the bar still said 300 until the moment it repainted, and the
 *  action underneath quietly shrank to a fifth of what its label promised.
 *
 *  When the window is the whole set, the intersection is exactly right and is
 *  what keeps a hidden or filtered-out card from staying selected.
 */
export function pruneSelection(
  selected: Set<number>,
  loaded: { id: number }[],
  total: number,
): Set<number> {
  if (selected.size === 0) return selected;
  if (loaded.length < total) return selected; // a window, not the whole set
  const present = new Set(loaded.map((p) => p.id));
  const kept = new Set<number>();
  for (const id of selected) {
    if (present.has(id)) kept.add(id);
  }
  return kept;
}

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
  const t = useT();
  const [properties, setProperties] = useState<Property[]>([]);
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [filters, setFilters] = useState<PropertyFilters>(DEFAULT_FILTERS);
  const [view, setView] = useState<ViewMode>("grid");
  // Real pagination: `properties` holds the pages fetched so far, `total` the
  // size of the whole filtered set. The grid used to download all of it — every
  // property with its market position, deal score and provenance computed — and
  // re-poll it every 30s, every 4s during a scan. Now it asks for a page and
  // extends as the user scrolls.
  //
  // The map is the exception and asks for everything (`limit: 0`): a map missing
  // every pin past the first page is not a map. So is "select all". Both are
  // one-off user actions, which is what makes them affordable — the poll was the
  // problem, not the occasional full read.
  const GRID_PAGE = 60;
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  // read inside refreshProperties without making it depend on `properties` —
  // that dependency would rebuild the callback on every fetch, and the effect
  // below would fire it again, forever
  const loadedCount = useRef(0);
  // set by a card's "View on map" jump so MapView centers on that property;
  // cleared on any manual view switch so the map fits the whole set again
  const [mapFocusId, setMapFocusId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Property | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [checkingBatch, setCheckingBatch] = useState(false);
  const [cancellingBatch, setCancellingBatch] = useState(false);
  const [batchProgress, setBatchProgress] = useState<AvailabilityCheckProgress | null>(null);
  const [batchSummary, setBatchSummary] = useState<AvailabilityCheckSummary | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  // a flag, not a message: the text is translated at render time, so switching
  // language repaints the banner without refetching the whole grid
  const [loadFailed, setLoadFailed] = useState(false);
  const [actionError, setActionError] = useState("");
  // monotonic id per refresh: typing in a filter fires overlapping requests,
  // and without this guard a slow older response would land after the newer
  // one and overwrite the grid with stale results
  const refreshSeq = useRef(0);
  // last `data_version` seen from the status endpoint; the poll refetches the
  // grid only when it differs. null = never read one yet.
  const dataVersion = useRef<string | null>(null);

  // Captured through a lazy initializer (not an effect) so the very first
  // render already has it — an effect would flash the grid without badges for
  // one frame. See `readSeenThreshold` for why the read is memoised.
  const [newSinceThreshold] = useState<string | null>(readSeenThreshold);

  // Only the property list depends on the filters, so it is the one thing the
  // per-keystroke path must refetch. Kept separate from the reference data
  // (profiles/settings/tags) below, which changes rarely — reloading all four
  // on every letter typed in a filter was pure waste.
  const refreshProperties = useCallback(async () => {
    const seq = ++refreshSeq.current;
    try {
      // The map needs every pin. The grid re-reads the pages it already has, so
      // a refresh triggered by a scan does not snap a scrolled-down user back
      // to the first page.
      const limit = view === "map" ? 0 : Math.max(GRID_PAGE, loadedCount.current);
      const page = await api.getProperties(filters, { limit, offset: 0 });
      if (seq !== refreshSeq.current) return; // a newer refresh superseded this one
      const props = page.items;
      loadedCount.current = props.length;
      setProperties(props);
      setTotal(page.total);
      setSelectedIds((prev) => pruneSelection(prev, props, page.total));
      setLoadFailed(false);
      // keep the open modal in sync with fresh data (e.g. after saving
      // notes or toggling favorite); if the property left the current
      // filter set, keep showing the stale copy until the user closes it
      setSelected((prev) =>
        prev ? props.find((p) => p.id === prev.id) ?? prev : prev
      );
    } catch (e) {
      if (seq !== refreshSeq.current) return;
      setLoadFailed(true);
    }
  }, [filters, view]);

  /** Append the next page. Guarded against the refresh running underneath it:
   *  if a newer refresh has started, its result is the truth and this page is
   *  dropped rather than concatenated onto a set it no longer belongs to. */
  const loadMore = useCallback(async () => {
    if (loadingMore) return;
    const seq = refreshSeq.current;
    setLoadingMore(true);
    try {
      const page = await api.getProperties(filters, {
        limit: GRID_PAGE,
        offset: loadedCount.current,
      });
      if (seq !== refreshSeq.current) return;
      setProperties((prev) => {
        const next = [...prev, ...page.items];
        loadedCount.current = next.length;
        return next;
      });
      setTotal(page.total);
    } catch {
      // leave the grid as it is; the sentinel stays and the user can retry
    } finally {
      setLoadingMore(false);
    }
  }, [filters, loadingMore]);

  // Reference data, independent of the filters: profiles, settings, tags and
  // scan status. A failure here must not clobber the "backend unreachable"
  // banner or blank the panels — the property fetch owns that error.
  const refreshMeta = useCallback(async () => {
    try {
      const [profs, status, sett, tagList] = await Promise.all([
        api.getProfiles(),
        api.getScanStatus(),
        api.getSettings(),
        api.getTags(),
      ]);
      setProfiles(profs);
      setScanStatus(status);
      setSettings(sett);
      setTags(tagList);
      // keep the poll's baseline in step: this call has just read the current
      // state, so the next tick must not mistake it for a change
      if (status.data_version) dataVersion.current = status.data_version;
    } catch {
      // best-effort: keep the last-known panels rather than emptying them
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([refreshProperties(), refreshMeta()]);
  }, [refreshProperties, refreshMeta]);

  // small debounce: `refreshProperties` changes on every keystroke in the
  // City/price filters, and only the list depends on them
  useEffect(() => {
    const t = window.setTimeout(refreshProperties, 250);
    return () => window.clearTimeout(t);
  }, [refreshProperties]);

  // load the reference data once on mount (the filter effect above never does)
  useEffect(() => {
    refreshMeta();
  }, [refreshMeta]);

  // Polling asks "did anything change?", not "give me everything again".
  //
  // The scan status is a cheap endpoint that touches two small aggregates, and
  // it carries a `data_version` fingerprint of the property set. Only when that
  // moves is the grid refetched. Before this, every tick re-downloaded the whole
  // filtered set with market position, match score, deal score and provenance
  // computed for each — every 4 seconds for as long as a scan ran.
  useEffect(() => {
    const ms = scanStatus?.running ? 4000 : 30000;
    const t = window.setInterval(async () => {
      try {
        const status = await api.getScanStatus();
        setScanStatus(status);
        if (status.data_version && status.data_version !== dataVersion.current) {
          // first poll of the session has nothing to compare against: adopt the
          // value rather than treating it as a change and refetching for nothing
          const known = dataVersion.current !== null;
          dataVersion.current = status.data_version;
          if (known) {
            refreshProperties();
            refreshMeta();
          }
        }
      } catch {
        // keep the last-known status; the property fetch owns the error banner
      }
    }, ms);
    return () => window.clearInterval(t);
  }, [scanStatus?.running, refreshProperties, refreshMeta]);

  // Fetch the next page as the sentinel below the grid scrolls into view. The
  // rootMargin pre-loads it before it is reached, so scrolling feels seamless
  // rather than paged.
  useEffect(() => {
    if (view !== "grid") return;
    const el = loadMoreRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadMore();
      },
      { rootMargin: "800px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [view, loadMore]);

  // a failed click must say so: without this wrapper the rejection is
  // unhandled and the button silently does nothing, which reads as "broken"
  async function runAction(fn: () => Promise<void>) {
    try {
      setActionError("");
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("common.actionFailed"));
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
    if (!confirm(t("app.confirmHideOne"))) {
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
      setProperties((list) =>
        // When the ⭐ Favorites filter is on and we just un-favorited it, the
        // card no longer belongs in the view: drop it now instead of leaving a
        // stale card with an empty star until the next background refresh.
        filters.only_favorites && !updated.is_favorite
          ? list.filter((x) => x.id !== p.id)
          : list.map((x) => (x.id === p.id ? updated : x))
      );
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

  /** "Select all" means the whole filtered set, not the pages on screen.
   *
   *  With the grid paginated, selecting only what is loaded would silently turn
   *  "hide all 300 results" into "hide the first 60" — the kind of quiet
   *  mismatch between the label and the action that this codebase avoids
   *  elsewhere by sharing one selection path. So it asks the backend for the
   *  full set (`limit: 0`), which is affordable precisely because it is a
   *  deliberate click and not the poll. */
  function toggleSelectAll() {
    if (selectedIds.size === total && total > 0) {
      setSelectedIds(new Set());
      return;
    }
    return runAction(async () => {
      const page = await api.getProperties(filters, { limit: 0 });
      setSelectedIds(new Set(page.items.map((p) => p.id)));
    });
  }

  function bulkAction(action: "hide" | "favorite" | "unfavorite" | "sold") {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (action === "hide" && !confirm(t("app.confirmHideMany", { count: ids.length }))) return;
    if (action === "sold" && !confirm(t("app.confirmSoldMany", { count: ids.length }))) return;
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
      setActionError(e instanceof Error ? e.message : t("app.batchCheckFailed"));
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
        {loadFailed && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm">
            ⚠️ {t("app.backendUnreachable")}
          </div>
        )}
        {actionError && (
          <div className="glass rounded-2xl p-4 border-rose-500/50 text-rose-600 dark:text-rose-300 text-sm flex items-center justify-between gap-3">
            <span>⚠️ {actionError}</span>
            <button data-action="app.error.dismiss" className="btn-ghost shrink-0" aria-label={t("common.dismissError")}
              onClick={() => setActionError("")}>✕</button>
          </div>
        )}

        <SearchProfiles profiles={profiles} settings={settings} onChanged={refresh} />

        {hasProfiles && <ScraperHealthPanel />}

        {hasProfiles && (
          <MarketVelocityPanel contract={filters.contract} city={filters.city} />
        )}

        {hasProfiles && (
          <PriceTrends contract={filters.contract} city={filters.city}
            onOpenProperty={setSelected} />
        )}

        {/* the whole filtered set, not the pages loaded so far */}
        <FiltersBar filters={filters} onChange={setFilters} count={total}
          view={view} onViewChange={changeView} profiles={profiles} tags={tags}
          matchEnabled={settings?.match_score_enabled ?? false}
          onReset={() => setFilters({ ...DEFAULT_FILTERS, contract: filters.contract })} />

        {properties.length === 0 && !loadFailed && (
          <div className="glass rounded-2xl p-6 sm:p-10 text-center t-muted">
            <p className="text-4xl mb-3">🏘️</p>
            <p className="font-medium t-strong">
              {hasProfiles ? t("app.noMatches") : t("app.welcome")}
            </p>
            {!hasProfiles && (
              <ol className="mt-4 text-sm text-left max-w-md mx-auto space-y-2">
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">1</span>
                  <span>
                    {t("app.step1")}{" "}
                    <strong>{t("app.step1Tip")}</strong> {t("app.step1TipBody")}
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">2</span>
                  <span>{t("app.step2")}</span>
                </li>
                <li className="flex gap-3">
                  <span className="shrink-0 w-6 h-6 rounded-full chip-blue text-xs flex items-center justify-center font-bold">3</span>
                  <span>{t("app.step3")}</span>
                </li>
              </ol>
            )}
            {hasProfiles && (
              <p className="text-sm mt-1">{t("app.noMatchesHint")}</p>
            )}
          </div>
        )}

        {/* Batch Selection & Live Availability Check Bar */}
        {properties.length > 0 && (
          <div className="glass rounded-2xl p-3 sm:p-4 flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button data-action="selection.toggleMode"
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
                  {selectionMode ? t("app.closeMultiSelect") : t("app.selectMultiple")}
                </button>
                {selectionMode && (
                  <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer ml-2">
                    <input data-action="selection.selectAll"
                      type="checkbox"
                      checked={selectedIds.size === total && total > 0}
                      onChange={() => toggleSelectAll()}
                    />
                    {t("app.selectAll", { selected: selectedIds.size, total })}
                  </label>
                )}
              </div>
              {selectionMode && selectedIds.size > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <button data-action="selection.hide"
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-rose-500 hover:text-rose-600 dark:hover:text-rose-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    title={t("app.hideSelectedTitle")}
                    onClick={() => bulkAction("hide")}>
                    {t("app.hideSelected", { count: selectedIds.size })}
                  </button>
                  <button data-action="selection.markSold"
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("sold")}>
                    {t("app.markSold", { count: selectedIds.size })}
                  </button>
                  <button data-action="selection.favorite"
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("favorite")}>
                    {t("app.addFavorites")}
                  </button>
                  <button data-action="selection.unfavorite"
                    type="button"
                    className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-amber-500 hover:text-amber-600 dark:hover:text-amber-400 flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={() => bulkAction("unfavorite")}>
                    {t("app.removeFavorites")}
                  </button>
                  <button data-action="selection.checkAvailability"
                    type="button"
                    className="accent-good text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5"
                    disabled={checkingBatch}
                    onClick={checkSelectedProperties}>
                    {checkingBatch
                      ? t("app.checking")
                      : t("app.checkAvailability", { count: selectedIds.size })}
                  </button>
                  {checkingBatch && (
                    <button data-action="selection.stopCheck"
                      type="button"
                      className="btn-ghost text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-rose-500 hover:text-rose-600 dark:hover:text-rose-400 flex items-center gap-1.5"
                      disabled={cancellingBatch}
                      onClick={stopCheckingProperties}>
                      {cancellingBatch ? t("app.stopping") : t("app.stop")}
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
                  ? t("app.checkProgress", {
                      done: batchProgress.done,
                      total: batchProgress.total,
                      online: batchProgress.online ?? 0,
                      gone: batchProgress.gone,
                    }) +
                    ((batchProgress.unknown ?? 0) > 0
                      ? t("app.checkProgressUnknown", { count: batchProgress.unknown ?? 0 })
                      : "")
                  : t("app.checkStarting")}{" "}
                {t("app.checkPacingNote")}
                {batchProgress?.transport && (
                  <span className="block opacity-75 font-normal">
                    {t("app.checkTransport", { transport: batchProgress.transport })}
                  </span>
                )}
                {batchProgress?.last_error && (
                  <span className="block opacity-75 font-normal">
                    {t("app.checkLastIssue", { error: batchProgress.last_error })}
                  </span>
                )}
              </ProgressBar>
            )}

            {batchSummary && !checkingBatch && (
              <div className="pt-2 border-t border-slate-200/50 dark:border-slate-700/50 text-xs t-muted flex items-center justify-between">
                <div>
                  {t("app.summaryChecked")} <strong>{batchSummary.checked}</strong> |{" "}
                  <span className="text-rose-600 dark:text-rose-400 font-bold">
                    {t("app.summaryGone", { count: batchSummary.gone })}
                  </span> |{" "}
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                    {t("app.summaryOnline", { count: batchSummary.online })}
                  </span>
                  {batchSummary.unknown > 0 && t("app.summaryUnknown", { count: batchSummary.unknown })}
                  {batchSummary.cancelled && (
                    <span className="block">{t("app.summaryCancelled")}</span>
                  )}
                  {batchSummary.aborted && !batchSummary.cancelled && (
                    <span className="block text-amber-600 dark:text-amber-400">
                      {t("app.summaryAborted")}
                      {batchSummary.transport && batchSummary.transport.includes("forced") && (
                        <span className="block font-normal opacity-90">
                          {t("app.summaryAbortedService", { transport: batchSummary.transport })}
                        </span>
                      )}
                      {batchSummary.transport && !batchSummary.transport.includes("window") && !batchSummary.transport.includes("forced") && (
                        <span className="block font-normal opacity-90">
                          {t("app.summaryAbortedNoWindow", { transport: batchSummary.transport })}
                        </span>
                      )}
                    </span>
                  )}
                  {batchSummary.capped && !batchSummary.aborted && !batchSummary.cancelled && (
                    <span className="block">{t("app.summaryCapped")}</span>
                  )}
                </div>
                <button data-action="selection.dismissSummary"
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
            {/* Fetches the next page as it scrolls into view (see the observer
                above); the button is the no-observer fallback and a manual
                nudge. Spans the whole grid row. */}
            {properties.length < total && (
              <div ref={loadMoreRef}
                className="col-span-full flex justify-center py-4">
                <button data-action="grid.loadMore" type="button" className="btn-ghost text-sm"
                  disabled={loadingMore}
                  onClick={() => loadMore()}>
                  {loadingMore
                    ? t("common.loading")
                    : t("app.showMoreCount", { count: total - properties.length })}
                </button>
              </div>
            )}
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
          auditEnabled={settings?.listing_audit_enabled ?? false}
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
