import type { PropertyFilters, ViewMode } from "../types";

interface Props {
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  count: number;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
}

export default function FiltersBar({
  filters, onChange, count, view, onViewChange,
}: Props) {
  const set = (patch: Partial<PropertyFilters>) =>
    onChange({ ...filters, ...patch });
  const isRent = filters.contract === "rent";

  return (
    // Two columns on a phone, free-flowing row from `sm` up. The `col-span-*`
    // classes below only bite in the grid: `grid-column` is inert on a flex
    // item, so the desktop layout ignores them without a breakpoint prefix.
    <section className="glass rounded-2xl p-4 grid grid-cols-2 items-end gap-3
      sm:flex sm:flex-wrap">
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
      <div className="col-span-2 flex flex-col gap-1">
        <label className="text-xs t-muted">City</label>
        <input className="input w-full sm:w-36" placeholder="e.g. Milan"
          value={filters.city} onChange={(e) => set({ city: e.target.value })} />
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
          <option value="match">🎯 Best match</option>
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs t-muted">Status</label>
        {/* "gone" = no longer seen by scans for days (sold/withdrawn);
            manually hidden properties never appear in "All" but can be viewed under "Discarded" */}
        <select className="input w-full sm:w-36" value={filters.status}
          onChange={(e) => set({ status: e.target.value })}>
          <option value="active">{isRent ? "For rent" : "For sale"}</option>
          <option value="filtered">🚫 Filtered</option>
          <option value="gone">💨 Gone</option>
          <option value="hidden">🙈 Discarded</option>
          <option value="all">All</option>
        </select>
      </div>
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
    </section>
  );
}
