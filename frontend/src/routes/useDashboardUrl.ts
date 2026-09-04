/** Reading and writing the dashboard's state through the address bar.
 *
 *  The filters, the sort and the view are held in the query string and the open
 *  property in the path, so there is one copy of them and the browser owns it.
 *  What that buys is not tidiness: it is a property that can be linked, a Back
 *  button that goes back, a reload that lands where it left, and two people
 *  looking at the same grid.
 *
 *  The two interesting decisions in here are what counts as a step in the
 *  history, and *when* each of these reads the state it is about to rewrite.
 */
import { useCallback, useMemo, useRef } from "react";
import { useMatch, useNavigate, useSearchParams } from "react-router-dom";
import type { PropertyFilters, ViewMode } from "../types";
import {
  FILTER_KEYS, LISTINGS, LOGS, SETTINGS, filtersFromSearch, propertyPath,
  searchFromState, viewFromSearch, withSearch,
} from "./params";

/** How long one edit stays "the same edit".
 *
 *  Typing "Bologna" into the city field is one thing the user did, not seven,
 *  and seven history entries would make Back a way of deleting a word rather
 *  than of undoing a decision. So a change to the same field as the last one,
 *  within this window, *replaces* the entry that change made; anything else
 *  pushes a new one. The first keystroke therefore pushes and the rest overwrite
 *  it — which leaves exactly one entry per field the user touched, holding the
 *  value they settled on, and Back returns to the grid as it was before they
 *  started typing.
 */
const SAME_EDIT_MS = 1000;

export interface DashboardUrl {
  filters: PropertyFilters;
  view: ViewMode;
  /** The property the URL has open, or null. */
  openPropertyId: number | null;
  setFilters: (next: PropertyFilters | ((current: PropertyFilters) => PropertyFilters)) => void;
  setView: (next: ViewMode) => void;
  openProperty: (id: number) => void;
  openSettings: () => void;
  openLogs: () => void;
  /** Back to the grid, keeping the filters as they stand when it is called. */
  close: () => void;
  /** Close whatever is open and land on the map, in one step: a "View on map"
   *  that navigated twice would compute the second address from the state
   *  before the first, and drop the view it had just asked for. */
  openMap: () => void;
}

export function useDashboardUrl(): DashboardUrl {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const propertyMatch = useMatch(`${LISTINGS}/:id`);

  const filters = useMemo(() => filtersFromSearch(params), [params]);
  const view = viewFromSearch(params);

  const openPropertyId = propertyMatch ? Number(propertyMatch.params.id) : null;

  /** The state as it is *now*, so the callbacks below read it at the moment they
   *  are called rather than at the moment they were created.
   *
   *  Not a micro-optimisation — a defect. Several of these are called from after
   *  an `await`: restoring a property closes its detail once the backend has
   *  answered, which can be a second later. A callback captured two renders ago
   *  carries the query string from two renders ago, so closing the detail
   *  navigated back to the filters that were applied when the button was
   *  *pressed* and silently undid a filter changed while the request was in
   *  flight. The grid returned to a status the user had already moved off, with
   *  nothing on screen to say why. Read here, written on every render, never
   *  read during one.
   */
  const now = useRef({ filters, view, search: "" });
  now.current = { filters, view, search: params.toString() };

  const lastEdit = useRef({ fields: "", at: 0 });

  const commit = useCallback((next: PropertyFilters, nextView: ViewMode) => {
    const { filters: current, view: currentView } = now.current;
    const fields = [
      ...FILTER_KEYS.filter((key) => next[key] !== current[key]),
      ...(nextView === currentView ? [] : ["view"]),
    ].join(",");
    // Nothing moved: a handler that re-sets the state it already had must not
    // put an identical entry in the history.
    if (!fields) return;
    const at = Date.now();
    const continuing = fields === lastEdit.current.fields && at - lastEdit.current.at < SAME_EDIT_MS;
    lastEdit.current = { fields, at };
    setParams(searchFromState(next, nextView), { replace: continuing });
  }, [setParams]);

  const setFilters = useCallback<DashboardUrl["setFilters"]>((next) => {
    const { filters: current, view: currentView } = now.current;
    commit(typeof next === "function" ? next(current) : next, currentView);
  }, [commit]);

  const setView = useCallback(
    (next: ViewMode) => commit(now.current.filters, next),
    [commit],
  );

  const go = useCallback(
    (path: string) => navigate(withSearch(path, now.current.search)),
    [navigate],
  );

  const openProperty = useCallback((id: number) => go(propertyPath(id)), [go]);
  const openSettings = useCallback(() => go(SETTINGS), [go]);
  const openLogs = useCallback(() => go(LOGS), [go]);
  const close = useCallback(() => go(LISTINGS), [go]);
  const openMap = useCallback(
    () => navigate(withSearch(LISTINGS, searchFromState(now.current.filters, "map").toString())),
    [navigate],
  );

  return {
    filters, view, openPropertyId,
    setFilters, setView, openProperty, openSettings, openLogs, close, openMap,
  };
}
