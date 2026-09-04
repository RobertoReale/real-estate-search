import { useEffect, useState } from "react";
import { useT } from "../i18n";
import {
  useCancelGeocode, useClearGeocodeCache, useGeocodeMissing, useGeocodeProgress,
} from "../queries/maintenance";
import { api, authToken, AuthError, fetchExport } from "../services/api";
import type { PropertyFilters, SearchProfile, Tag, ViewMode } from "../types";
import { groupSearchProfiles } from "../utils/searchProfiles";
import { ProgressBar } from "./ProgressBar";


interface Props {
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  count: number;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
  profiles: SearchProfile[];
  tags: Tag[];
  // "Best match" ranks by the Smart Match Score, which is off unless the user
  // configured a dream home. Offering the sort while it is disabled is a dead
  // option: the backend has no score to order by and silently leaves the grid
  // unsorted (see main.py `sort == "match"`).
  matchEnabled: boolean;
  // Clears every filter back to defaults (App keeps the Buy/Rent choice).
  onReset: () => void;
}

export default function FiltersBar({
  filters, onChange, count, view, onViewChange, profiles, tags, matchEnabled,
  onReset,
}: Props) {
  const t = useT();
  // The two maintenance sweeps and the one that stops them. What each of them
  // is doing, whether it failed and what it answered are the mutation's own
  // state now, so there is no `finally` left that can forget to clear a flag.
  const geocode = useGeocodeMissing();
  const clearCache = useClearGeocodeCache();
  const cancelGeocode = useCancelGeocode();
  const [stoppingGeocode, setStoppingGeocode] = useState(false);
  const geocoding = geocode.isPending;
  const geocodeProgress = useGeocodeProgress(geocoding);
  const geocodeResult = geocode.data ?? null;
  const cacheCleared = clearCache.data?.cleared ?? null;
  // A backend older than these routes answers 404, and "update the backend"
  // is a far more useful thing to read than "Error 404".
  const failure = geocode.error ?? clearCache.error;
  const geocodeError = !failure
    ? null
    : /Error 404|Not Found/i.test(failure.message)
      ? t("filters.backendTooOld")
      : failure.message;
  // only used on the authenticated export path, which is a fetch rather than a
  // navigation and so has a wait and a failure the UI has to show
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  // Advanced filters live behind a toggle so the common controls stay
  // uncluttered. Opened by default when one is already active (e.g. after a
  // reload), so an applied filter is never hidden.
  const advActiveCount =
    (filters.portal ? 1 : 0) + (filters.agency ? 1 : 0) +
    (filters.deal ? 1 : 0) + (filters.min_sqm_price ? 1 : 0) +
    (filters.max_sqm_price ? 1 : 0) + (filters.merged_only ? 1 : 0);
  const [advOpen, setAdvOpen] = useState(advActiveCount > 0);

  const set = (patch: Partial<PropertyFilters>) =>
    onChange({ ...filters, ...patch });
  const isRent = filters.contract === "rent";

  // Whether anything is narrowing the grid right now — drives the "Reset
  // filters" affordance (contract and the default Newest sort don't count:
  // reset keeps the Buy/Rent world the user is in).
  const anyFilterActive =
    !!filters.q || !!filters.city || !!filters.zone || !!filters.min_price ||
    !!filters.max_price || !!filters.min_sqm || !!filters.max_sqm ||
    !!filters.floor_band || !!filters.rooms || !!filters.source ||
    !!filters.tag || !!filters.profile_id || filters.only_price_drops ||
    filters.only_favorites || filters.status !== "active" ||
    filters.sort !== "newest" || advActiveCount > 0 || !!filters.geo_mode;

  // Turning the dream home off (or never setting it up) must not strand the
  // grid on a "Best match" sort that no longer does anything: fall back to
  // Newest so the list stays in a defined order and the select has a match.
  useEffect(() => {
    if (!matchEnabled && filters.sort === "match") set({ sort: "newest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchEnabled, filters.sort]);

  /** Hand a URL to the browser: opened in a tab for the print-ready PDF report
   *  (which raises the print dialog on load — downloaded, it would print
   *  nothing), saved via a transient anchor for the three file formats. */
  function handOff(url: string, fmt: string, filename?: string) {
    if (fmt === "pdf") {
      window.open(url, "_blank", "noreferrer");
      return;
    }
    const a = document.createElement("a");
    a.href = url;
    a.rel = "noreferrer";
    if (filename) a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function exportAs(fmt: "html" | "markdown" | "csv" | "pdf") {
    const what = filters.only_favorites
      ? t("filters.exportFavorites")
      : isRent
        ? t("filters.exportRentals")
        : t("filters.exportProperties");
    const title = filters.city ? t("filters.exportIn", { what, city: filters.city }) : what;
    setExportError(null);

    // The common case (no API token): let the browser fetch it. Content-
    // Disposition names the file and the PDF prints itself, with no blob in
    // between — the path this has always taken.
    if (!authToken.get()) {
      handOff(api.exportUrl(filters, fmt, title), fmt);
      return;
    }
    // With the token on, that navigation cannot carry the Authorization header
    // and every export came back 401 — the dossier arrived as a page of JSON.
    // Fetch it authenticated instead and hand the browser the result.
    setExporting(fmt);
    try {
      const { blob, filename } = await fetchExport(filters, fmt, title);
      const url = URL.createObjectURL(blob);
      handOff(url, fmt, filename);
      // long enough for the tab/download to have taken it; revoking
      // immediately cancels the transfer in some browsers
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      // an AuthError has already raised the token prompt; anything else is the
      // backend's own message, and a button that silently does nothing reads
      // as broken
      if (!(e instanceof AuthError)) {
        setExportError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setExporting(null);
    }
  }

  return (
    // Two columns on a phone, free-flowing row from `sm` up. The `col-span-*`
    // classes below only bite in the grid: `grid-column` is inert on a flex
    // item, so the desktop layout ignores them without a breakpoint prefix.
    <section className="glass rounded-2xl p-4 grid grid-cols-2 items-end gap-3
      sm:flex sm:flex-wrap">
      {/* Free-text search spans the full width on both layouts: it is the
          fastest way to prune a cluttered dashboard ("San Siro", "nuova
          costruzione") and searches title, zone, address and the ad text. */}
      <div className="col-span-2 w-full flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-q">{t("filters.search")}</label>
        <div className="relative">
          <input data-action="filters.query"
            id="filter-q"
            className={`input w-full ${filters.q ? "pr-9" : ""}`}
            placeholder={t("filters.searchPlaceholder")}
            value={filters.q}
            onChange={(e) => set({ q: e.target.value })}
          />
          {filters.q && (
            <button data-action="filters.query.clear"
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 t-muted hover:t-strong text-lg leading-none px-1"
              aria-label={t("filters.clearSearch")}
              onClick={() => set({ q: "" })}>
              ✕
            </button>
          )}
        </div>
      </div>
      {/* Buy/Rent are separate worlds (different price scales, different
          goals), so the toggle is the most prominent control */}
      <div className="col-span-2 flex flex-col gap-1">
        {/* A <label> names a form control; these three are button groups, so
            the name goes on a role="group" instead — a <label> with no `for`
            is announced as nothing at all. */}
        <span className="text-xs t-muted">{t("filters.market")}</span>
        <div role="group" aria-label={t("filters.market")}
          className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
          <button data-action="filters.contract.sale"
            className={`flex-1 sm:flex-none px-3 py-2 text-sm font-medium transition ${
              !isRent
                ? "bg-blue-600 text-white"
                : "bg-white text-slate-500 hover:text-slate-800 dark:bg-slate-800/80 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
            onClick={() => set({ contract: "sale" })}>
            {t("filters.buy")}
          </button>
          <button data-action="filters.contract.rent"
            className={`flex-1 sm:flex-none px-3 py-2 text-sm font-medium transition ${
              isRent
                ? "bg-teal-600 text-white"
                : "bg-white text-slate-500 hover:text-slate-800 dark:bg-slate-800/80 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
            onClick={() => set({ contract: "rent" })}>
            {t("filters.rent")}
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-city">{t("filters.city")}</label>
        <input data-action="filters.city" id="filter-city" className="input w-full sm:w-32" placeholder={t("filters.cityPlaceholder")}
          value={filters.city} onChange={(e) => set({ city: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-zone">{t("filters.zone")}</label>
        <input data-action="filters.zone" id="filter-zone" className="input w-full sm:w-32" placeholder={t("filters.zonePlaceholder")}
          value={filters.zone} onChange={(e) => set({ zone: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-min-price">
          {t("filters.minPrice")} {isRent && t("filters.perMonth")}
        </label>
        <input data-action="filters.minPrice" id="filter-min-price" className="input w-full sm:w-28" type="number" placeholder="0"
          value={filters.min_price} onChange={(e) => set({ min_price: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-max-price">
          {t("filters.maxPrice")} {isRent && t("filters.perMonth")}
        </label>
        <input data-action="filters.maxPrice" id="filter-max-price" className="input w-full sm:w-28" type="number" placeholder="∞"
          value={filters.max_price} onChange={(e) => set({ max_price: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-min-sqm">{t("filters.minSqm")}</label>
        <input data-action="filters.minSqm" id="filter-min-sqm" className="input w-full sm:w-20" type="number" placeholder="0"
          value={filters.min_sqm} onChange={(e) => set({ min_sqm: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-max-sqm">{t("filters.maxSqm")}</label>
        <input data-action="filters.maxSqm" id="filter-max-sqm" className="input w-full sm:w-20" type="number" placeholder="∞"
          value={filters.max_sqm} onChange={(e) => set({ max_sqm: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-rooms">{t("filters.rooms")}</label>
        <select data-action="filters.rooms" id="filter-rooms" className="input w-full sm:w-24" value={filters.rooms}
          onChange={(e) => set({ rooms: e.target.value })}>
          <option value="">{t("common.all")}</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      {/* Floor bands, parsed server-side from the messy free-text floor label
          ("piano terra", "3", "attico"): a listing whose floor can't be read
          matches no band and drops out while this is set. */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-floor">{t("filters.floor")}</label>
        <select data-action="filters.floor" id="filter-floor" className="input w-full sm:w-36" value={filters.floor_band}
          onChange={(e) => set({
            floor_band: e.target.value as PropertyFilters["floor_band"],
          })}>
          <option value="">{t("filters.anyFloor")}</option>
          <option value="ground">{t("filters.floorGround")}</option>
          <option value="low">{t("filters.floorLow")}</option>
          <option value="mid">{t("filters.floorMid")}</option>
          <option value="high">{t("filters.floorHigh")}</option>
          <option value="top">{t("filters.floorTop")}</option>
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-sort">{t("filters.sortBy")}</label>
        <select data-action="filters.sort" id="filter-sort" className="input w-full sm:w-40" value={filters.sort}
          onChange={(e) => set({ sort: e.target.value })}>
          <option value="newest">{t("filters.sortNewest")}</option>
          <option value="price_asc">{t("filters.sortPriceAsc")}</option>
          <option value="price_desc">{t("filters.sortPriceDesc")}</option>
          <option value="sqm_price">{t("filters.sortSqmPrice")}</option>
          {matchEnabled && <option value="match">{t("filters.sortMatch")}</option>}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-status">{t("filters.status")}</label>
        {/* "gone" = no longer seen by scans for days (inferred exit);
            "sold" = user confirmed the sale; manually hidden/sold properties
            never appear in "All" but each has its own filter here */}
        <select data-action="filters.status" id="filter-status" className="input w-full sm:w-36" value={filters.status}
          onChange={(e) => set({ status: e.target.value })}>
          <option value="active">
            {isRent ? t("filters.statusForRent") : t("filters.statusForSale")}
          </option>
          <option value="filtered">{t("filters.statusFiltered")}</option>
          <option value="gone">{t("filters.statusGone")}</option>
          <option value="sold">
            {isRent ? t("filters.statusRentedOut") : t("filters.statusSold")}
          </option>
          <option value="hidden">{t("filters.statusHidden")}</option>
          <option value="all">{t("filters.statusAll")}</option>
        </select>
      </div>
      {/* Origin: tell inbox imports apart from monitored-search finds — the
          two are otherwise indistinguishable once accepted (source column). */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted" htmlFor="filter-origin">{t("filters.origin")}</label>
        <select data-action="filters.source" id="filter-origin" className="input w-full sm:w-36" value={filters.source}
          onChange={(e) => set({ source: e.target.value as PropertyFilters["source"] })}>
          <option value="">{t("filters.originAll")}</option>
          <option value="scan">{t("filters.originScan")}</option>
          <option value="email">{t("filters.originEmail")}</option>
        </select>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="filter-tag">{t("filters.tag")}</label>
          <select data-action="filters.tag" id="filter-tag" className="input w-full sm:w-36" value={filters.tag}
            onChange={(e) => set({ tag: e.target.value })}>
            <option value="">{t("filters.allTags")}</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.name}>{tag.name} ({tag.count})</option>
            ))}
          </select>
        </div>
      )}
      {/* Overlay a saved monitored search on the WHOLE grid (imports included):
          applies its city/contract and its exclusion keywords, so the same
          rules that keep scans clean can prune email imports too. */}
      {profiles.length > 0 && (
        <div className="flex flex-col gap-1">
          {/* This is a FILTER, not a sort: it narrows the grid to the
              properties a saved search actually found (its "🔍 Found by"
              provenance), not everything that merely matches its city and
              contract. The label used to read "Match a search", which was
              mistaken for a "best match" ranking. */}
          <label className="text-xs t-muted" htmlFor="filter-profile">{t("filters.limitToSearch")}</label>
          <select data-action="filters.profile" id="filter-profile" className="input w-full sm:w-44" value={filters.profile_id}
            title={t("filters.limitToSearchTitle")}
            onChange={(e) => set({ profile_id: e.target.value })}>
            <option value="">{t("filters.allSearches")}</option>
            {groupSearchProfiles(profiles).map((g) => (
              <option key={g.ids[0]} value={String(g.ids[0])}>
                {g.baseName} {g.portals.length > 1 ? `(${g.portals.join("/")})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="col-span-2 flex flex-wrap gap-x-5 gap-y-1 sm:flex-col sm:gap-1 sm:pb-2">
        <label className="flex items-center gap-2 text-sm t-body cursor-pointer">
          <input data-action="filters.priceDrops" type="checkbox" checked={filters.only_price_drops}
            onChange={(e) => set({ only_price_drops: e.target.checked })} />
          {t("filters.priceDrops")}
        </label>
        <label className="flex items-center gap-2 text-sm t-body cursor-pointer">
          <input data-action="filters.favorites" type="checkbox" checked={filters.only_favorites}
            onChange={(e) => set({ only_favorites: e.target.checked })} />
          {t("filters.favorites")}
        </label>
        {/* Gateway to the advanced filters — kept next to the checkboxes so the
            common controls above stay uncluttered. The badge shows how many
            advanced filters are active even while the panel is collapsed. */}
        <button data-action="filters.advanced.toggle" type="button"
          className="flex items-center gap-1.5 text-sm accent-link hover:underline"
          aria-expanded={advOpen}
          onClick={() => setAdvOpen((o) => !o)}>
          {t("filters.more")}
          {advActiveCount > 0 && (
            <span className="chip-blue text-[11px] px-1.5 py-0.5 rounded-full font-semibold">
              {advActiveCount}
            </span>
          )}
          <span className="t-dim">{advOpen ? "▲" : "▼"}</span>
        </button>
      </div>

      {advOpen && (
        <div className="col-span-2 w-full p-3 sm:p-4 rounded-xl panel
          grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap animate-fade-in">
          <p className="col-span-2 w-full text-xs font-medium t-muted -mb-1">
            {t("filters.moreTitle")}{" "}
            <span className="font-normal t-dim">{t("filters.moreHint")}</span>
          </p>
          {/* Portal: a card can group ads from several portals, so this keeps
              the ones present on the chosen portal (see main.py `portal=`). */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-portal">{t("filters.portal")}</label>
            <select data-action="filters.portal" id="filter-portal" className="input w-full sm:w-40" value={filters.portal}
              onChange={(e) => set({
                portal: e.target.value as PropertyFilters["portal"],
              })}>
              <option value="">{t("filters.anyPortal")}</option>
              <option value="immobiliare">Immobiliare</option>
              <option value="idealista">Idealista</option>
            </select>
          </div>
          <div className="flex flex-col gap-1 col-span-2 sm:col-span-1">
            <label className="text-xs t-muted" htmlFor="filter-agency">{t("filters.agency")}</label>
            <input data-action="filters.agency" id="filter-agency" className="input w-full sm:w-48" placeholder={t("filters.agencyPlaceholder")}
              value={filters.agency} onChange={(e) => set({ agency: e.target.value })} />
          </div>
          {/* Deal quality reads the Deal Score (€/sqm gap vs the local median).
              "Fair or better" drops the overpriced; both need a local median,
              so unscored cards fall out when set. */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-deal">{t("filters.deal")}</label>
            <select data-action="filters.deal" id="filter-deal" className="input w-full sm:w-44" value={filters.deal}
              onChange={(e) => set({
                deal: e.target.value as PropertyFilters["deal"],
              })}>
              <option value="">{t("filters.anyDeal")}</option>
              <option value="undervalued">{t("filters.dealUndervalued")}</option>
              <option value="fair_plus">{t("filters.dealFairPlus")}</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-min-sqm-price">{t("filters.minSqmPrice")}</label>
            <input data-action="filters.minSqmPrice" id="filter-min-sqm-price" className="input w-full sm:w-24" type="number" placeholder="0"
              value={filters.min_sqm_price}
              onChange={(e) => set({ min_sqm_price: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted" htmlFor="filter-max-sqm-price">{t("filters.maxSqmPrice")}</label>
            <input data-action="filters.maxSqmPrice" id="filter-max-sqm-price" className="input w-full sm:w-24" type="number" placeholder="∞"
              value={filters.max_sqm_price}
              onChange={(e) => set({ max_sqm_price: e.target.value })} />
          </div>
          <label className="col-span-2 flex items-center gap-2 text-sm t-body cursor-pointer min-h-11 sm:min-h-0 sm:pb-2">
            <input data-action="filters.mergedOnly" type="checkbox" checked={filters.merged_only}
              onChange={(e) => set({ merged_only: e.target.checked })} />
            {t("filters.mergedOnly")}
          </label>
        </div>
      )}

      {/* Count, maintenance, export and the view switch. `flex-wrap` is what
          keeps them on the page: four groups whose combined width is ~540px
          cannot share one row on a 390px phone, and without wrapping the last
          of them (the Grid/Map switch) pushed the whole document sideways. */}
      <div className="col-span-2 flex flex-wrap items-end justify-between gap-3
        sm:ml-auto sm:justify-start">
        <div className="flex flex-col gap-1 justify-end pb-2">
          <span className="text-sm t-muted">{t("filters.countProperties", { count })}</span>
          {anyFilterActive && (
            <button data-action="filters.reset"
              type="button"
              className="text-xs accent-link hover:underline text-left"
              onClick={onReset}
              title={t("filters.resetTitle")}>
              {t("filters.reset")}
            </button>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium t-muted">{t("filters.maintenance")}</span>
          <button data-action="maintenance.geocode"
            className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
              geocoding
                ? "bg-slate-200 dark:bg-slate-800 text-slate-500 border-slate-300 dark:border-slate-700 cursor-wait animate-pulse"
                : "bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border-sky-500/30"
            }`}
            disabled={geocoding}
            title={t("filters.findCoordsTitle")}
            onClick={() => {
              // Both notices belong to one press, so the other one's answer
              // goes with it: a "2 addresses forgotten" left under a fresh
              // sweep reads as something this run just did.
              clearCache.reset();
              setStoppingGeocode(false);
              // The grid carries the coordinates, so the mutation re-reads it.
              geocode.mutate(undefined, { onSettled: () => setStoppingGeocode(false) });
            }}>
            {geocoding ? t("filters.locating") : t("filters.findCoords")}
          </button>
          <button data-action="maintenance.clearGeocodeCache"
            className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
              clearCache.isPending
                ? "bg-slate-200 dark:bg-slate-800 text-slate-500 border-slate-300 dark:border-slate-700 cursor-wait animate-pulse"
                : "bg-slate-500/10 hover:bg-slate-500/20 text-slate-600 dark:text-slate-300 border-slate-500/30"
            }`}
            disabled={clearCache.isPending || geocoding}
            title={t("filters.retryFailedTitle")}
            onClick={() => {
              geocode.reset();
              clearCache.mutate();
            }}>
            {clearCache.isPending ? t("filters.clearing") : t("filters.retryFailed")}
          </button>
        </div>
        {/* Export the filtered set as a shareable offline file (no server, no
            DB) — see services/exporter.py */}
        <div className="flex flex-col gap-1">
          <span className="text-xs t-muted">{t("filters.export")} {count > 0 && `(${count})`}</span>
          <div role="group" aria-label={t("filters.export")}
            className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
            {/* The action id is carried in the tuple rather than built from
                `fmt`: the inventory is checked against the literal strings in
                the source, and a template one would be invisible to it. */}
            {([
              ["html", "HTML", "export.html"],
              ["markdown", "MD", "export.markdown"],
              ["csv", "CSV", "export.csv"],
              ["pdf", "PDF", "export.pdf"],
            ] as const).map(
              ([fmt, label, action]) => (
                <button key={fmt} data-action={action}
                  className="px-3 py-2 text-sm font-medium transition bg-white
                    text-slate-500 hover:text-slate-800 dark:bg-slate-800/80
                    dark:text-slate-400 dark:hover:text-slate-200
                    disabled:opacity-40 disabled:cursor-not-allowed"
                  disabled={count === 0 || exporting !== null}
                  title={
                    fmt === "pdf"
                      ? t("filters.exportPdfTitle", { count })
                      : t("filters.exportTitle", { count, format: label })
                  }
                  onClick={() => exportAs(fmt)}>
                  {exporting === fmt ? "…" : label}
                </button>
              ),
            )}
          </div>
        </div>
        {/* view switch: the map only shows geolocated listings, so the grid
            stays the authoritative view (see MapView's "without coordinates") */}
        <div className="flex flex-col gap-1">
          <span className="text-xs t-muted">{t("filters.view")}</span>
          <div role="group" aria-label={t("filters.view")}
            className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
            {([
              ["grid", t("filters.viewGrid"), "view.grid"],
              ["map", t("filters.viewMap"), "view.map"],
            ] as const).map(
              ([value, label, action]) => (
                <button key={value} data-action={action}
                  className={`px-3 py-2 text-sm font-medium transition ${
                    view === value
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-500 hover:text-slate-800 dark:bg-slate-800/80 dark:text-slate-400 dark:hover:text-slate-200"
                  }`}
                  onClick={() => onViewChange(value)}>
                  {label}
                </button>
              ),
            )}
          </div>
        </div>
      </div>

      {geocoding && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 animate-fade-in shadow-sm space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
              <span>📍</span> {t("filters.geocodeRunning")}
            </span>
            <button data-action="maintenance.geocode.stop"
              className="btn py-1 px-2.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition disabled:opacity-40 flex items-center gap-1"
              disabled={stoppingGeocode}
              onClick={() => {
                // Held until the sweep itself ends rather than until this
                // request answers: the button says "stopping", and the sweep
                // only stops at its next poll.
                setStoppingGeocode(true);
                cancelGeocode.mutate(undefined, { onError: () => {} });
              }}>
              {stoppingGeocode ? t("app.stopping") : t("app.stop")}
            </button>
          </div>
          <ProgressBar
            done={geocodeProgress?.done ?? 0}
            total={geocodeProgress?.total ?? 0}
            indeterminate={!geocodeProgress || geocodeProgress.total <= 0}>
            {geocodeProgress
              ? t("filters.geocodeProgress", {
                  done: geocodeProgress.done,
                  total: geocodeProgress.total,
                  geocoded: geocodeProgress.geocoded,
                  cached: geocodeProgress.cached,
                }) +
                (geocodeProgress.not_found > 0
                  ? t("filters.geocodeProgressNotFound", { count: geocodeProgress.not_found })
                  : "")
              : t("filters.geocodeStarting")}
            {" "}
            <span className="opacity-75 font-normal">{t("filters.geocodePacing")}</span>
            {geocodeProgress?.last_error && (
              <span className="block opacity-75 font-normal text-rose-600 dark:text-rose-400">
                {t("filters.geocodeLastIssue", { error: geocodeProgress.last_error })}
              </span>
            )}
          </ProgressBar>
        </div>
      )}

      {exportError && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <p role="status" className="text-rose-700 dark:text-rose-300">
            ❌ {t("filters.exportFailed", { error: exportError })}
          </p>
          <button data-action="export.error.dismiss"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => setExportError(null)}
            title={t("common.close")}>
            ✕
          </button>
        </div>
      )}

      {geocodeError && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <p className="text-rose-700 dark:text-rose-300">❌ {geocodeError}</p>
          <button data-action="maintenance.error.dismiss"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => { geocode.reset(); clearCache.reset(); }}
            title={t("common.close")}>
            ✕
          </button>
        </div>
      )}

      {cacheCleared !== null && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-slate-500/10 border border-slate-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <p>
            {cacheCleared === 0
              ? t("filters.cacheClearedNone")
              : t(cacheCleared === 1 ? "filters.cacheClearedOne" : "filters.cacheCleared", {
                  count: cacheCleared,
                })}
          </p>
          <button data-action="maintenance.cacheCleared.dismiss"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => clearCache.reset()}
            title={t("common.close")}>
            ✕
          </button>
        </div>
      )}

      {geocodeResult && !geocoding && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <div className="space-y-1">
            <p className="font-semibold text-sky-700 dark:text-sky-400 text-sm flex items-center gap-1.5">
              <span>📍</span> {t("filters.geocodeDone")}
            </p>
            {geocodeResult.scanned === 0 ? (
              <p>{t("filters.geocodeNothing")}</p>
            ) : (
              <p>
                {t("filters.geocodeLocated", {
                  geocoded: geocodeResult.geocoded,
                  scanned: geocodeResult.scanned,
                })}
                {geocodeResult.not_found > 0 &&
                  t("filters.geocodeNotFound", { count: geocodeResult.not_found })}
                .
                {geocodeResult.cancelled ? (
                  <span className="block mt-1 font-medium text-amber-600 dark:text-amber-400">
                    {t("filters.geocodeCancelled")}
                  </span>
                ) : geocodeResult.remaining > 0 ? (
                  <> {t("filters.geocodeRemaining", { count: geocodeResult.remaining })}</>
                ) : null}
              </p>
            )}
          </div>
          <button data-action="maintenance.result.dismiss"
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => geocode.reset()}
            title={t("common.close")}>
            ✕
          </button>
        </div>
      )}
    </section>
  );
}
