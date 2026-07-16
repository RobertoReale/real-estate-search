import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { PropertyFilters, SearchProfile, ViewMode } from "../types";

interface Props {
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  count: number;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
  profiles: SearchProfile[];
  // "Best match" ranks by the Smart Match Score, which is off unless the user
  // configured a dream home. Offering the sort while it is disabled is a dead
  // option: the backend has no score to order by and silently leaves the grid
  // unsorted (see main.py `sort == "match"`).
  matchEnabled: boolean;
}

export default function FiltersBar({
  filters, onChange, count, view, onViewChange, profiles, matchEnabled,
}: Props) {
  const [repairing, setRepairing] = useState(false);
  const [repairResult, setRepairResult] = useState<{
    properties_fixed: number;
    listings_fixed: number;
    images_recovered: number;
    properties_merged: number;
    duplicate_listings_removed: number;
  } | null>(null);

  const set = (patch: Partial<PropertyFilters>) =>
    onChange({ ...filters, ...patch });
  const isRent = filters.contract === "rent";

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
          {/* the magnifier is only an affordance for the empty field; once the
              user is typing it is redundant (and the ✕ takes its place) */}
          {!filters.q && (
            <span className="absolute left-3 top-1/2 -translate-y-1/2 t-muted pointer-events-none">🔍</span>
          )}
          <input
            className={`input w-full ${filters.q ? "" : "pl-9"}`}
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
        <label className="text-xs t-muted">Rooms</label>
        <select className="input w-full sm:w-24" value={filters.rooms}
          onChange={(e) => set({ rooms: e.target.value })}>
          <option value="">All</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
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
            {profiles.map((p) => (
              <option key={p.id} value={String(p.id)}>{p.name}</option>
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
      </div>

      <div className="col-span-2 flex items-end justify-between gap-3 sm:ml-auto sm:justify-start">
        <span className="text-sm t-muted pb-2">{count} properties</span>
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
    </section>
  );
}
