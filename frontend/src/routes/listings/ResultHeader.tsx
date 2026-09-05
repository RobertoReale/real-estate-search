/** The line above the results: how many there are, in what order, in what shape.
 *
 *  Three controls and deliberately no fourth. This row used to be the tail of
 *  the filter bar and carried the exports, the two maintenance sweeps and the
 *  reset as well — seven groups competing for the top of the screen, none of
 *  them about the results underneath. What is left is the three questions a
 *  reader has about a list they are looking at; the rest went to the rail
 *  (export, which acts on the query) and to the searches screen (maintenance,
 *  which acts on the database).
 */
import { useEffect } from "react";
import { useT } from "../../i18n";
import type { PropertyFilters, ViewMode } from "../../types";

interface Props {
  /** The size of the whole filtered set, not of the pages loaded so far. */
  count: number;
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  view: ViewMode;
  onViewChange: (view: ViewMode) => void;
  /** "Best match" ranks by the Smart Match Score, which is off unless the user
   *  configured a dream home. Offering the sort while it is disabled is a dead
   *  option: the backend has no score to order by and silently leaves the grid
   *  unsorted (see main.py `sort == "match"`). */
  matchEnabled: boolean;
}

export default function ResultHeader({
  count, filters, onChange, view, onViewChange, matchEnabled,
}: Props) {
  const t = useT();

  // Turning the dream home off (or never setting it up) must not strand the
  // grid on a "Best match" sort that no longer does anything: fall back to
  // Newest so the list stays in a defined order and the select has a match.
  useEffect(() => {
    if (!matchEnabled && filters.sort === "match") onChange({ ...filters, sort: "newest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchEnabled, filters.sort]);

  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <span className="text-sm t-muted">{t("filters.countProperties", { count })}</span>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="filter-sort">{t("filters.sortBy")}</label>
          <select data-action="filters.sort" id="filter-sort" className="input w-full sm:w-40"
            value={filters.sort}
            onChange={(e) => onChange({ ...filters, sort: e.target.value })}>
            <option value="newest">{t("filters.sortNewest")}</option>
            <option value="price_asc">{t("filters.sortPriceAsc")}</option>
            <option value="price_desc">{t("filters.sortPriceDesc")}</option>
            <option value="sqm_price">{t("filters.sortSqmPrice")}</option>
            {matchEnabled && <option value="match">{t("filters.sortMatch")}</option>}
          </select>
        </div>
        {/* The map only shows geolocated listings, so the grid stays the
            authoritative view (see MapView's "without coordinates"). */}
        <div className="flex flex-col gap-1">
          <span className="text-xs t-muted">{t("filters.view")}</span>
          <div role="group" aria-label={t("filters.view")}
            className="flex rounded-lg overflow-hidden border border-line-strong">
            {([
              ["grid", t("filters.viewGrid"), "view.grid"],
              ["map", t("filters.viewMap"), "view.map"],
            ] as const).map(
              ([value, label, action]) => (
                <button key={value} data-action={action}
                  className={`px-3 py-2 text-sm font-medium transition ${
                    view === value
                      ? "bg-accent text-on-solid"
                      : "bg-control text-ink-dim hover:text-ink-strong"
                  }`}
                  onClick={() => onViewChange(value)}>
                  {label}
                </button>
              ),
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
