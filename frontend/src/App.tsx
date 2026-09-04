/** Root application dashboard component orchestrating global layout and state.
 *  Manages live property listings, search filters, view modes (Grid / Map),
 *  search profile diagnostics, and the overlays the URL opens over it.
 *
 *  It reads and writes nothing itself: every fetch on this screen is a keyed
 *  query or a mutation in `src/queries/`, and the filters, the sort, the view
 *  and the open property are held in the address bar (`routes/params.ts`). What
 *  is left in this component is the one thing neither the server nor the URL
 *  owns — which properties are ticked for a batch action, which is a choice in
 *  progress rather than a place. */
import { useMemo, useRef, useState } from "react";
import { Outlet } from "react-router-dom";
import FiltersBar from "./components/FiltersBar";
import MapView from "./components/MapView";
import MarketVelocityPanel from "./components/MarketVelocity";
import Navbar from "./components/Navbar";
import PriceTrends from "./components/PriceTrends";
import ScraperHealthPanel from "./components/ScraperHealth";
import { ProgressBar } from "./components/ProgressBar";
import PropertyCard from "./components/PropertyCard";
import SearchProfiles from "./components/SearchProfiles";
import { useDebounced } from "./hooks/useDebounced";
import { useOnReveal } from "./hooks/useOnReveal";
import {
  useDataVersionSync, useProfiles, useScanStatus, useTags, useTriggerScan,
} from "./queries/dashboard";
import { useGeocodeMissing } from "./queries/maintenance";
import {
  useAddTag, useAvailabilityProgress, useBulkProperties, useCancelPropertiesCheck,
  useCheckProperties, useFetchPropertySet, useHideProperty, usePropertyPages,
  usePropertySet, useRemoveTag, useRefreshDashboard, useToggleFavorite,
} from "./queries/properties";
import { useSettings } from "./queries/settings";
import { useT } from "./i18n";
import type { DashboardContext } from "./routes/context";
import { DEFAULT_FILTERS } from "./routes/params";
import { useDashboardUrl } from "./routes/useDashboardUrl";
import type { Property, ViewMode } from "./types";

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
 *  only when what is in hand is all of it.
 *
 *  "Select all" means the whole filtered set and asks the backend for it
 *  (`limit: 0`), while the grid keeps holding one window. Intersecting the
 *  selection against that window on the next refresh — which any scan triggers,
 *  and the poll every 30s — silently turned "hide all 300 results" into "hide
 *  the first 60": the bar still said 300 until the moment it repainted, and the
 *  action underneath quietly shrank to a fifth of what its label promised.
 *
 *  When the window is the whole set, the intersection is exactly right and is
 *  what keeps a hidden or filtered-out card from staying selected. Applied on
 *  the way out rather than written back into the selection: the raw set is what
 *  the user picked, and pruning it in place would make an unlucky refresh
 *  destroy a choice they could not have known was fragile.
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

export default function App() {
  const t = useT();
  // The filters, the sort, the view and the open property are the URL's, so
  // they survive a reload, move under Back and Forward, and can be sent to
  // somebody else. Everything below is state that genuinely is not a place.
  const {
    filters, setFilters, view, setView, openPropertyId,
    openProperty, openSettings, openLogs, close, openMap,
  } = useDashboardUrl();
  // set by a card's "View on map" jump so MapView centers on that property;
  // cleared on any manual view switch so the map fits the whole set again
  const [mapFocusId, setMapFocusId] = useState<number | null>(null);
  const [rawSelection, setRawSelection] = useState<Set<number>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [cancellingBatch, setCancellingBatch] = useState(false);
  const [actionError, setActionError] = useState("");
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  // Captured through a lazy initializer (not an effect) so the very first
  // render already has it — an effect would flash the grid without badges for
  // one frame. See `readSeenThreshold` for why the read is memoised.
  const [newSinceThreshold] = useState<string | null>(readSeenThreshold);

  // The key the grid is read by, one step behind the form. Only the property
  // list depends on the filters, so it is the one thing a keystroke can cost a
  // request — and debouncing the key means the intermediate queries are never
  // created rather than created and discarded.
  const query = useDebounced(filters, 250);
  const onMap = view === "map";

  // The grid holds a window; the map holds every pin, because a map missing
  // everything past the first page is not a map. Two queries rather than one
  // with a variable limit: they are different reads and they are cached apart.
  const grid = usePropertyPages(query, !onMap);
  const wholeSet = usePropertySet(query, onMap);

  const answered = useMemo<Property[]>(
    () => (onMap
      ? wholeSet.data?.items ?? []
      : grid.data?.pages.flatMap((page) => page.items) ?? []),
    [onMap, wholeSet.data, grid.data],
  );
  // The size of the whole filtered set, not of what is loaded: the count above
  // the grid, "select all", and the export all mean this number.
  const answeredTotal = (onMap ? wholeSet.data?.total : grid.data?.pages[0]?.total) ?? 0;
  const loadFailed = onMap ? wholeSet.isError : grid.isError;

  // A refused refresh must not blank the grid. The answer that did arrive is
  // still the best thing on offer, and the banner above it says it is stale —
  // whereas an empty page cannot be told apart from "nothing matches", which is
  // the one reading that would send the user to change their filters. Written
  // on every render that produced an answer, so it is always the newest one.
  const lastAnswer = useRef({ items: [] as Property[], total: 0 });
  if (!loadFailed) lastAnswer.current = { items: answered, total: answeredTotal };
  const properties = loadFailed ? lastAnswer.current.items : answered;
  const total = loadFailed ? lastAnswer.current.total : answeredTotal;

  const profiles = useProfiles().data ?? [];
  const tags = useTags().data ?? [];
  const settings = useSettings().data ?? null;
  const scanStatus = useScanStatus().data ?? null;
  // The grid is re-read when the backend's fingerprint of the property set
  // moves, and only then.
  useDataVersionSync(scanStatus ?? undefined);

  const refresh = useRefreshDashboard();
  const fetchWholeSet = useFetchPropertySet();
  const triggerScan = useTriggerScan();
  const geocodeMissing = useGeocodeMissing();
  const hideProperty = useHideProperty();
  const toggleFavoriteOn = useToggleFavorite();
  const addTagTo = useAddTag();
  const removeTagFrom = useRemoveTag();
  const bulk = useBulkProperties();
  const checkBatch = useCheckProperties();
  const cancelBatch = useCancelPropertiesCheck();
  const batchProgress = useAvailabilityProgress(checkBatch.isPending);

  // What the selection means right now. Derived rather than stored, so a
  // background refresh can never quietly shrink what the batch bar promises —
  // see `pruneSelection` for the version of this that did.
  const selectedIds = useMemo(
    () => pruneSelection(rawSelection, properties, total),
    [rawSelection, properties, total],
  );

  // Fetch the next page as the sentinel below the grid scrolls into view.
  useOnReveal(
    loadMoreRef,
    !onMap && grid.hasNextPage && !grid.isFetchingNextPage,
    () => { void grid.fetchNextPage(); },
  );

  // a failed click must say so: without this wrapper the rejection is
  // unhandled and the button silently does nothing, which reads as "broken"
  async function runAction(fn: () => Promise<unknown>) {
    try {
      setActionError("");
      await fn();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("common.actionFailed"));
    }
  }

  // "Find coordinates" from the map's zone-filter banner: the batch geocoder
  // backfills pins for the properties a geographic filter would otherwise drop.
  function findCoordinates() {
    if (geocodeMissing.isPending) return;
    return runAction(() => geocodeMissing.mutateAsync());
  }

  function scanNow() {
    return runAction(() => triggerScan.mutateAsync());
  }

  function quickHide(p: Property) {
    // same confirm() used by the modal's "Hide property" action: hiding is
    // irreversible on its own (only a manual "Restore" brings it back), so
    // both entry points must ask the same way
    if (!confirm(t("app.confirmHideOne"))) {
      return;
    }
    return runAction(async () => {
      await hideProperty.mutateAsync(p.id);
      if (openPropertyId === p.id) close();
    });
  }

  function toggleFavorite(p: Property) {
    // The ⭐ Favorites filter is part of the query, so a card that no longer
    // belongs in the view leaves it with the refetch rather than being spliced
    // out of a local list.
    return runAction(() => toggleFavoriteOn.mutateAsync(p));
  }

  function addTag(p: Property, name: string) {
    return runAction(() => addTagTo.mutateAsync({ property: p, name }));
  }

  function removeTag(p: Property, tagId: number) {
    return runAction(() => removeTagFrom.mutateAsync({ property: p, tagId }));
  }

  // "View on map" from the property detail: focus the map on this property and
  // switch view. The property is already in the current grid, so it is on the
  // map too (the detail geocodes it first when it had no pin, and the grid
  // re-reads).
  // One navigation, not two: closing the detail and switching the view are the
  // same step, and `openMap` is what makes them one address.
  function showOnMap(p: Property) {
    setMapFocusId(p.id);
    openMap();
  }

  // Any manual view switch drops the "View on map" focus, so the map goes back
  // to fitting the whole filtered set instead of staying zoomed on one pin.
  function changeView(v: ViewMode) {
    setMapFocusId(null);
    setView(v);
  }

  /** "Select all" means the whole filtered set, not the pages on screen.
   *
   *  With the grid paginated, selecting only what is loaded would silently turn
   *  "hide all 300 results" into "hide the first 60" — the kind of quiet
   *  mismatch between the label and the action that this codebase avoids
   *  elsewhere by sharing one selection path. So it reads the full set
   *  (`limit: 0`), which is affordable precisely because it is a deliberate
   *  click and not the poll. */
  function toggleSelectAll() {
    if (selectedIds.size === total && total > 0) {
      setRawSelection(new Set());
      return;
    }
    return runAction(async () => {
      const page = await fetchWholeSet(query);
      setRawSelection(new Set(page.items.map((p) => p.id)));
    });
  }

  function toggleOne(id: number) {
    setRawSelection((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  function bulkAction(action: "hide" | "favorite" | "unfavorite" | "sold") {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    if (action === "hide" && !confirm(t("app.confirmHideMany", { count: ids.length }))) return;
    if (action === "sold" && !confirm(t("app.confirmSoldMany", { count: ids.length }))) return;
    return runAction(async () => {
      await bulk.mutateAsync({ ids, action });
      setRawSelection(new Set());
      setSelectionMode(false);
    });
  }

  async function checkSelectedProperties() {
    const ids = [...selectedIds];
    if (ids.length === 0) return;
    setCancellingBatch(false);
    setActionError("");
    try {
      await checkBatch.mutateAsync(ids);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : t("app.batchCheckFailed"));
    } finally {
      setCancellingBatch(false);
    }
  }

  // The running batch owns the portal connection on its own thread, so this
  // can only ask it to stop after the property currently in flight -- there
  // is no way to cancel a live socket call from here. `cancellingBatch` just
  // disables the button so a second click can't fire a redundant request
  // while the batch (still pending) winds down.
  function stopCheckingProperties() {
    setCancellingBatch(true);
    cancelBatch.mutate(undefined, {
      onError: () => {
        // best-effort: if this request itself fails, the batch simply keeps
        // running to completion, same as if the button had never been clicked
      },
    });
  }

  const hasProfiles = profiles.length > 0;
  const checkingBatch = checkBatch.isPending;
  const batchSummary = checkBatch.data ?? null;

  // What an overlay is handed: the rows already in hand, and the writes that
  // belong to this screen. A detail view opened from a card therefore costs no
  // request, and a favourite toggled inside it is the same act as one toggled on
  // the card behind it rather than a second implementation of it.
  const dashboard: DashboardContext = {
    properties, tags, settings, toggleFavorite, addTag, removeTag, showOnMap, close,
  };

  return (
    <div className="min-h-screen">
      <Navbar
        scanStatus={scanStatus}
        onScanNow={scanNow}
        onOpenSettings={openSettings}
        onOpenLogs={openLogs}
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
            onOpenProperty={(p) => openProperty(p.id)} />
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
                    if (selectionMode) setRawSelection(new Set());
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
                  onClick={() => checkBatch.reset()}>
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
              onSelect={(p) => openProperty(p.id)}
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
              geocoding={geocodeMissing.isPending}
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
                onToggleSelect={selectionMode ? () => toggleOne(p.id) : undefined}
                onClick={() => {
                  if (selectionMode) toggleOne(p.id);
                  else openProperty(p.id);
                }}
                onQuickHide={() => quickHide(p)}
                onToggleFavorite={() => toggleFavorite(p)}
                allTags={tags}
                onAddTag={(name) => addTag(p, name)}
                onRemoveTag={(tagId) => removeTag(p, tagId)}
              />
            ))}
            {/* Fetches the next page as it scrolls into view (see `useOnReveal`
                above); the button is the no-observer fallback and a manual
                nudge. Spans the whole grid row.
                It stays mounted and operable while that page is on its way:
                a control that disables itself under the focus that just
                reached it is one a keyboard user cannot press at all, and a
                second press costs nothing — the query answers both with the
                request already in flight. */}
            {(grid.hasNextPage || grid.isFetchingNextPage) && (
              <div ref={loadMoreRef}
                className="col-span-full flex justify-center py-4">
                <button data-action="grid.loadMore" type="button" className="btn-ghost text-sm"
                  aria-busy={grid.isFetchingNextPage}
                  onClick={() => grid.fetchNextPage()}>
                  {grid.isFetchingNextPage
                    ? t("common.loading")
                    : t("app.showMoreCount", { count: total - properties.length })}
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Whatever the URL has open over the dashboard: a property, the settings,
          the log. Rendered last, as the modals it replaced were — a dialog
          appended after the grid is one the Tab key reaches by going forward,
          which is the order a screen reader announces it in too. */}
      <Outlet context={dashboard} />
    </div>
  );
}
