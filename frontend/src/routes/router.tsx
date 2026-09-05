/** Every address the app answers to.
 *
 *  Two layers of layout route, and both are load-bearing.
 *
 *  `AppShell` is the outer one: the header, the navigation and the event stream
 *  belong to the session rather than to a screen, so they mount once and every
 *  destination is drawn inside them.
 *
 *  `App` — the listings grid — is the inner one, and it has no path of its own.
 *  That is what lets the URL move between the grid, a property, the settings
 *  and the log without re-running the grid's queries, losing the scroll
 *  position or emptying a multi-selection, which is exactly what a table that
 *  swapped one whole screen for another would do. Insights and Searches sit
 *  beside it rather than under it: they *are* whole screens, and a user on them
 *  is not looking at the grid.
 */
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import App from "../App";
import LogViewer from "../components/LogViewer";
import SettingsModal from "../components/SettingsModal";
import AppShell from "../ui/AppShell";
import { useDashboard } from "./context";
import InsightsRoute from "./InsightsRoute";
import { INSIGHTS, LISTINGS, LOGS, SEARCHES, SETTINGS, withSearch } from "./params";
import PropertyRoute from "./PropertyRoute";
import SearchesRoute from "./SearchesRoute";

function SettingsRoute() {
  return <SettingsModal onClose={useDashboard().close} />;
}

function LogsRoute() {
  return <LogViewer onClose={useDashboard().close} />;
}

/** "/" and anything nobody recognises. The filters are carried across, because
 *  the one address a person is most likely to type by hand is the bare one, and
 *  arriving at a grid that has quietly dropped what the link asked for is worse
 *  than a 404. */
function ToListings() {
  return <Navigate to={withSearch(LISTINGS, useLocation().search)} replace />;
}

export default function AppRoutes() {
  return (
    // `useTransitions={false}`: the router wraps its state updates in
    // `startTransition` by default, which is right when a navigation swaps one
    // page for another and wrong here, because the address bar *is* the filter
    // form. Deferred, the checkbox a user has just clicked stays visibly
    // unticked until the grid behind it has finished re-rendering — React
    // restores a controlled input to its last rendered value, and the value it
    // was rendered with is the one the pending transition has not applied yet.
    // A control that ignores the click that operated it reads as a broken
    // control, however briefly, and the heavier the grid the longer it lasts.
    <BrowserRouter useTransitions={false}>
      <Routes>
        <Route element={<AppShell />}>
          <Route element={<App />}>
            <Route path={LISTINGS} element={null} />
            <Route path={`${LISTINGS}/:id`} element={<PropertyRoute />} />
            <Route path={SETTINGS} element={<SettingsRoute />} />
            <Route path={LOGS} element={<LogsRoute />} />
          </Route>
          <Route path={INSIGHTS} element={<InsightsRoute />} />
          <Route path={SEARCHES} element={<SearchesRoute />} />
        </Route>
        <Route path="*" element={<ToListings />} />
      </Routes>
    </BrowserRouter>
  );
}
