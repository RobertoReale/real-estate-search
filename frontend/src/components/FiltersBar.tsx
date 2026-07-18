import { useEffect, useState } from "react";
import { useProgressPoll } from "../hooks/useProgressPoll";
import { api } from "../services/api";
import type { GeocodeProgress, GeocodeSummary, PropertyFilters, SearchProfile, Tag, ViewMode } from "../types";
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
  const [repairing, setRepairing] = useState(false);
  const [repairResult, setRepairResult] = useState<{
    properties_fixed: number;
    listings_fixed: number;
    images_recovered: number;
    properties_merged: number;
    duplicate_listings_removed: number;
  } | null>(null);
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeResult, setGeocodeResult] = useState<GeocodeSummary | null>(null);
  const [geocodeError, setGeocodeError] = useState<string | null>(null);
  const [geocodeProgress, setGeocodeProgress] = useState<GeocodeProgress | null>(null);
  const [stoppingGeocode, setStoppingGeocode] = useState(false);
  // Advanced filters live behind a toggle so the common controls stay
  // uncluttered. Opened by default when one is already active (e.g. after a
  // reload), so an applied filter is never hidden.
  const advActiveCount =
    (filters.portal ? 1 : 0) + (filters.agency ? 1 : 0) +
    (filters.deal ? 1 : 0) + (filters.min_sqm_price ? 1 : 0) +
    (filters.max_sqm_price ? 1 : 0) + (filters.merged_only ? 1 : 0);
  const [advOpen, setAdvOpen] = useState(advActiveCount > 0);

  useProgressPoll(
    geocoding,
    api.geocodeProgress,
    (prog) => {
      if (prog.active) setGeocodeProgress(prog);
    },
    800,
  );

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
    filters.sort !== "newest" || advActiveCount > 0;

  // Turning the dream home off (or never setting it up) must not strand the
  // grid on a "Best match" sort that no longer does anything: fall back to
  // Newest so the list stays in a defined order and the select has a match.
  useEffect(() => {
    if (!matchEnabled && filters.sort === "match") set({ sort: "newest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchEnabled, filters.sort]);

  function exportAs(fmt: "html" | "markdown" | "csv") {
    const what = filters.only_favorites ? "Favorites" : isRent ? "Rentals" : "Properties";
    const title = filters.city ? `${what} in ${filters.city}` : what;
    // A file download (Content-Disposition attachment): navigating to it starts
    // the download without leaving the page, so a transient anchor is enough.
    const a = document.createElement("a");
    a.href = api.exportUrl(filters, fmt, title);
    a.rel = "noreferrer";
    document.body.appendChild(a);
    a.click();
    a.remove();
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
        <label className="text-xs t-muted">Search</label>
        <div className="relative">
          <input
            className={`input w-full ${filters.q ? "pr-9" : ""}`}
            placeholder="Search by zone, address, title, floor or ad text…"
            value={filters.q}
            onChange={(e) => set({ q: e.target.value })}
          />
          {filters.q && (
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 t-muted hover:t-strong text-lg leading-none px-1"
              aria-label="Clear search"
              onClick={() => set({ q: "" })}>
              ✕
            </button>
          )}
        </div>
      </div>
      {/* Buy/Rent are separate worlds (different price scales, different
          goals), so the toggle is the most prominent control */}
      <div className="col-span-2 flex flex-col gap-1">
        <label className="text-xs t-muted">Market</label>
        <div className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
          <button
            className={`flex-1 sm:flex-none px-3 py-2 text-sm font-medium transition ${
              !isRent
                ? "bg-blue-600 text-white"
                : "bg-white text-slate-500 hover:text-slate-800 dark:bg-slate-800/80 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
            onClick={() => set({ contract: "sale" })}>
            🏠 Buy
          </button>
          <button
            className={`flex-1 sm:flex-none px-3 py-2 text-sm font-medium transition ${
              isRent
                ? "bg-teal-600 text-white"
                : "bg-white text-slate-500 hover:text-slate-800 dark:bg-slate-800/80 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
            onClick={() => set({ contract: "rent" })}>
            🔑 Rent
          </button>
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">City</label>
        <input className="input w-full sm:w-32" placeholder="e.g. Milan"
          value={filters.city} onChange={(e) => set({ city: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Zone</label>
        <input className="input w-full sm:w-32" placeholder="e.g. Navigli"
          value={filters.zone} onChange={(e) => set({ zone: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">
          Min price € {isRent && "/mo"}
        </label>
        <input className="input w-full sm:w-28" type="number" placeholder="0"
          value={filters.min_price} onChange={(e) => set({ min_price: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">
          Max price € {isRent && "/mo"}
        </label>
        <input className="input w-full sm:w-28" type="number" placeholder="∞"
          value={filters.max_price} onChange={(e) => set({ max_price: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Min sqm</label>
        <input className="input w-full sm:w-20" type="number" placeholder="0"
          value={filters.min_sqm} onChange={(e) => set({ min_sqm: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Max sqm</label>
        <input className="input w-full sm:w-20" type="number" placeholder="∞"
          value={filters.max_sqm} onChange={(e) => set({ max_sqm: e.target.value })} />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Rooms</label>
        <select className="input w-full sm:w-24" value={filters.rooms}
          onChange={(e) => set({ rooms: e.target.value })}>
          <option value="">All</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      {/* Floor bands, parsed server-side from the messy free-text floor label
          ("piano terra", "3", "attico"): a listing whose floor can't be read
          matches no band and drops out while this is set. */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Floor</label>
        <select className="input w-full sm:w-36" value={filters.floor_band}
          onChange={(e) => set({
            floor_band: e.target.value as PropertyFilters["floor_band"],
          })}>
          <option value="">Any floor</option>
          <option value="ground">Ground floor</option>
          <option value="low">Low (1–2)</option>
          <option value="mid">Middle (3–5)</option>
          <option value="high">High (6+)</option>
          <option value="top">Top floor (attico/ultimo)</option>
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Sort by</label>
        <select className="input w-full sm:w-40" value={filters.sort}
          onChange={(e) => set({ sort: e.target.value })}>
          <option value="newest">Newest</option>
          <option value="price_asc">Price ascending</option>
          <option value="price_desc">Price descending</option>
          <option value="sqm_price">Lowest €/sqm</option>
          {matchEnabled && <option value="match">🎯 Best match</option>}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Status</label>
        {/* "gone" = no longer seen by scans for days (inferred exit);
            "sold" = user confirmed the sale; manually hidden/sold properties
            never appear in "All" but each has its own filter here */}
        <select className="input w-full sm:w-36" value={filters.status}
          onChange={(e) => set({ status: e.target.value })}>
          <option value="active">{isRent ? "For rent" : "For sale"}</option>
          <option value="filtered">🚫 Filtered</option>
          <option value="gone">💨 Gone</option>
          <option value="sold">🔑 {isRent ? "Rented out" : "Sold"}</option>
          <option value="hidden">🙈 Discarded</option>
          <option value="all">All</option>
        </select>
      </div>
      {/* Origin: tell inbox imports apart from monitored-search finds — the
          two are otherwise indistinguishable once accepted (source column). */}
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Origin</label>
        <select className="input w-full sm:w-36" value={filters.source}
          onChange={(e) => set({ source: e.target.value as PropertyFilters["source"] })}>
          <option value="">All sources</option>
          <option value="scan">🔎 Monitored search</option>
          <option value="email">✉️ Email import</option>
        </select>
      </div>
      {tags.length > 0 && (
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">Tag</label>
          <select className="input w-full sm:w-36" value={filters.tag}
            onChange={(e) => set({ tag: e.target.value })}>
            <option value="">All tags</option>
            {tags.map((t) => (
              <option key={t.id} value={t.name}>{t.name} ({t.count})</option>
            ))}
          </select>
        </div>
      )}
      {/* Overlay a saved monitored search on the WHOLE grid (imports included):
          applies its city/contract and its exclusion keywords, so the same
          rules that keep scans clean can prune email imports too. */}
      {profiles.length > 0 && (
        <div className="flex flex-col gap-1">
          {/* This is a FILTER, not a sort: it narrows the grid to what one of
              your saved searches would keep (its city, contract and excluded
              keywords), imports included. The label used to read "Match a
              search", which was mistaken for a "best match" ranking. */}
          <label className="text-xs t-muted">Limit to a search</label>
          <select className="input w-full sm:w-44" value={filters.profile_id}
            title="Filter the grid down to what a saved search would keep: applies its city, contract and excluded keywords (useful to prune email imports the scan filter never saw). This narrows the list — it does not reorder it."
            onChange={(e) => set({ profile_id: e.target.value })}>
            <option value="">All searches</option>
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
          <input type="checkbox" checked={filters.only_price_drops}
            onChange={(e) => set({ only_price_drops: e.target.checked })} />
          📉 Price drops
        </label>
        <label className="flex items-center gap-2 text-sm t-body cursor-pointer">
          <input type="checkbox" checked={filters.only_favorites}
            onChange={(e) => set({ only_favorites: e.target.checked })} />
          ⭐ Favorites
        </label>
        {/* Gateway to the advanced filters — kept next to the checkboxes so the
            common controls above stay uncluttered. The badge shows how many
            advanced filters are active even while the panel is collapsed. */}
        <button type="button"
          className="flex items-center gap-1.5 text-sm accent-link hover:underline"
          aria-expanded={advOpen}
          onClick={() => setAdvOpen((o) => !o)}>
          ⚙️ More filters
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
            More filters <span className="font-normal t-dim">· narrow the grid by portal, agency, deal quality or €/sqm</span>
          </p>
          {/* Portal: a card can group ads from several portals, so this keeps
              the ones present on the chosen portal (see main.py `portal=`). */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Portal</label>
            <select className="input w-full sm:w-40" value={filters.portal}
              onChange={(e) => set({
                portal: e.target.value as PropertyFilters["portal"],
              })}>
              <option value="">Any portal</option>
              <option value="immobiliare">Immobiliare</option>
              <option value="idealista">Idealista</option>
            </select>
          </div>
          <div className="flex flex-col gap-1 col-span-2 sm:col-span-1">
            <label className="text-xs t-muted">Agency</label>
            <input className="input w-full sm:w-48" placeholder="e.g. Tecnocasa"
              value={filters.agency} onChange={(e) => set({ agency: e.target.value })} />
          </div>
          {/* Deal quality reads the Deal Score (€/sqm gap vs the local median).
              "Fair or better" drops the overpriced; both need a local median,
              so unscored cards fall out when set. */}
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Deal</label>
            <select className="input w-full sm:w-44" value={filters.deal}
              onChange={(e) => set({
                deal: e.target.value as PropertyFilters["deal"],
              })}>
              <option value="">Any deal</option>
              <option value="undervalued">💎 Undervalued only</option>
              <option value="fair_plus">👍 Fair or better</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Min €/sqm</label>
            <input className="input w-full sm:w-24" type="number" placeholder="0"
              value={filters.min_sqm_price}
              onChange={(e) => set({ min_sqm_price: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Max €/sqm</label>
            <input className="input w-full sm:w-24" type="number" placeholder="∞"
              value={filters.max_sqm_price}
              onChange={(e) => set({ max_sqm_price: e.target.value })} />
          </div>
          <label className="col-span-2 flex items-center gap-2 text-sm t-body cursor-pointer min-h-11 sm:min-h-0 sm:pb-2">
            <input type="checkbox" checked={filters.merged_only}
              onChange={(e) => set({ merged_only: e.target.checked })} />
            🔗 Merged only (same home on several portals/agencies)
          </label>
        </div>
      )}

      <div className="col-span-2 flex items-end justify-between gap-3 sm:ml-auto sm:justify-start">
        <div className="flex flex-col gap-1 justify-end pb-2">
          <span className="text-sm t-muted">{count} properties</span>
          {anyFilterActive && (
            <button
              type="button"
              className="text-xs accent-link hover:underline text-left"
              onClick={onReset}
              title="Clear every filter and go back to the default view">
              ↺ Reset filters
            </button>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium t-muted">Maintenance</label>
          <button
            className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
              repairing
                ? "bg-slate-200 dark:bg-slate-800 text-slate-500 border-slate-300 dark:border-slate-700 cursor-wait animate-pulse"
                : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border-amber-500/30"
            }`}
            disabled={repairing}
            title="Instantly repair missing titles, zones and photos on previously imported listings"
            onClick={async () => {
              setRepairing(true);
              setRepairResult(null);
              try {
                const res = await api.repairListings();
                setRepairResult(res);
                onChange({ ...filters });
              } finally {
                setRepairing(false);
              }
            }}>
            {repairing ? "⏳ Repairing…" : "🛠️ Repair data"}
          </button>
          <button
            className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
              geocoding
                ? "bg-slate-200 dark:bg-slate-800 text-slate-500 border-slate-300 dark:border-slate-700 cursor-wait animate-pulse"
                : "bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-400 border-sky-500/30"
            }`}
            disabled={geocoding}
            title="Find map coordinates for listings that have an address or zone but no pin (uses OpenStreetMap; can take a while)"
            onClick={async () => {
              setGeocoding(true);
              setGeocodeResult(null);
              setGeocodeError(null);
              setGeocodeProgress(null);
              setStoppingGeocode(false);
              try {
                const res = await api.geocodeMissing();
                setGeocodeResult(res);
                onChange({ ...filters });
              } catch (e) {
                const raw = e instanceof Error ? e.message : String(e);
                setGeocodeError(
                  /Error 404|Not Found/i.test(raw)
                    ? "The backend doesn't have this feature yet — restart it (close and re-run start.bat / serve.bat) and try again."
                    : raw,
                );
              } finally {
                setGeocoding(false);
                setGeocodeProgress(null);
                setStoppingGeocode(false);
              }
            }}>
            {geocoding ? "⏳ Locating…" : "📍 Find coordinates"}
          </button>
        </div>
        {/* Export the filtered set as a shareable offline file (no server, no
            DB) — see services/exporter.py */}
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">Export {count > 0 && `(${count})`}</label>
          <div className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
            {([["html", "HTML"], ["markdown", "MD"], ["csv", "CSV"]] as const).map(
              ([fmt, label]) => (
                <button key={fmt}
                  className="px-3 py-2 text-sm font-medium transition bg-white
                    text-slate-500 hover:text-slate-800 dark:bg-slate-800/80
                    dark:text-slate-400 dark:hover:text-slate-200
                    disabled:opacity-40 disabled:cursor-not-allowed"
                  disabled={count === 0}
                  title={`Download the ${count} filtered properties as ${label}`}
                  onClick={() => exportAs(fmt)}>
                  {label}
                </button>
              ),
            )}
          </div>
        </div>
        {/* view switch: the map only shows geolocated listings, so the grid
            stays the authoritative view (see MapView's "without coordinates") */}
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">View</label>
          <div className="flex rounded-lg overflow-hidden border border-slate-300 dark:border-slate-600/60">
            {([["grid", "▦ Grid"], ["map", "🗺 Map"]] as const).map(
              ([value, label]) => (
                <button key={value}
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

      {repairResult && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <div className="space-y-1">
            {repairResult.properties_fixed > 0 || repairResult.listings_fixed > 0 || repairResult.images_recovered > 0 || repairResult.properties_merged > 0 || repairResult.duplicate_listings_removed > 0 ? (
              <>
                <p className="font-semibold text-amber-700 dark:text-amber-400 text-sm flex items-center gap-1.5">
                  <span>✅</span> Repair completed successfully!
                </p>
                <p>
                  Updated <strong>{repairResult.properties_fixed} properties</strong>,{" "}
                  <strong>{repairResult.listings_fixed} listings</strong> and recovered{" "}
                  <strong>{repairResult.images_recovered} photos</strong>.
                  {(repairResult.properties_merged > 0 || repairResult.duplicate_listings_removed > 0) && (
                    <>
                      {" "}Merged <strong>{repairResult.properties_merged} duplicate cards</strong>{" "}
                      and removed <strong>{repairResult.duplicate_listings_removed} duplicate listings</strong>{" "}
                      pointing at the same ad.
                    </>
                  )}
                </p>
              </>
            ) : (
              <>
                <p className="font-semibold text-emerald-600 dark:text-emerald-400 text-sm flex items-center gap-1.5">
                  <span>✨</span> Everything is in order and fully in sync!
                </p>
                <p>
                  The check scanned the database: no property or listing with missing data, city (`Location N/A`), photos, or duplicate ad links was found to repair. Every listing is already complete and aligned.
                </p>
              </>
            )}
          </div>
          <button
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => setRepairResult(null)}
            title="Close">
            ✕
          </button>
        </div>
      )}

      {geocoding && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 animate-fade-in shadow-sm space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
              <span>📍</span> Locating coordinates in background…
            </span>
            <button
              className="btn py-1 px-2.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition disabled:opacity-40 flex items-center gap-1"
              disabled={stoppingGeocode}
              onClick={async () => {
                setStoppingGeocode(true);
                try {
                  await api.cancelGeocode();
                } catch {
                  // ignore
                }
              }}>
              {stoppingGeocode ? "Stopping…" : "⏹ Stop"}
            </button>
          </div>
          <ProgressBar
            done={geocodeProgress?.done ?? 0}
            total={geocodeProgress?.total ?? 0}
            indeterminate={!geocodeProgress || geocodeProgress.total <= 0}>
            {geocodeProgress
              ? `Locating listing ${geocodeProgress.done} of ${geocodeProgress.total} — ${geocodeProgress.geocoded} located, ${geocodeProgress.cached} from cache${geocodeProgress.not_found > 0 ? `, ${geocodeProgress.not_found} not found` : ""}`
              : "Starting coordinate lookup…"}
            {" "}
            <span className="opacity-75 font-normal">
              (Paced at 1 request/sec to respect OpenStreetMap Nominatim usage policy)
            </span>
            {geocodeProgress?.last_error && (
              <span className="block opacity-75 font-normal text-rose-600 dark:text-rose-400">
                Last issue from Nominatim: {geocodeProgress.last_error}
              </span>
            )}
          </ProgressBar>
        </div>
      )}

      {geocodeError && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <p className="text-rose-700 dark:text-rose-300">❌ {geocodeError}</p>
          <button
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => setGeocodeError(null)}
            title="Close">
            ✕
          </button>
        </div>
      )}

      {geocodeResult && !geocoding && (
        <div className="col-span-2 mt-3 p-3.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-xs text-slate-800 dark:text-slate-200 flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <div className="space-y-1">
            <p className="font-semibold text-sky-700 dark:text-sky-400 text-sm flex items-center gap-1.5">
              <span>📍</span> Coordinate lookup finished
            </p>
            {geocodeResult.scanned === 0 ? (
              <p>
                Nothing to locate: every property either already has a pin or has
                no address/zone to look one up from. (A bare city is skipped on
                purpose — it would drop every such listing on one downtown pin.)
              </p>
            ) : (
              <p>
                Located <strong>{geocodeResult.geocoded}</strong> of{" "}
                {geocodeResult.scanned} listings without a pin
                {geocodeResult.not_found > 0 && <> · {geocodeResult.not_found} could not be resolved</>}.
                {geocodeResult.cancelled ? (
                  <span className="block mt-1 font-medium text-amber-600 dark:text-amber-400">
                    ⏹ Stopped — remaining properties were left without pins. Click "Find coordinates" again to resume.
                  </span>
                ) : geocodeResult.remaining > 0 ? (
                  <> <strong>{geocodeResult.remaining}</strong> left — run it again to continue.</>
                ) : null}
              </p>
            )}
          </div>
          <button
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-base leading-none font-bold p-1"
            onClick={() => setGeocodeResult(null)}
            title="Close">
            ✕
          </button>
        </div>
      )}
    </section>
  );
}
