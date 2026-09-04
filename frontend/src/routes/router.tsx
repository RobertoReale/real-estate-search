/** Every address the dashboard answers to.
 *
 *  The table is deliberately small and deliberately flat: one screen, and the
 *  three things that open on top of it. What matters is the shape rather than
 *  the size — the dashboard is a *layout* route with no path of its own, so it
 *  mounts once and stays mounted while the URL moves between the overlays.
 *  Opening Settings and closing it again therefore does not re-run the grid's
 *  queries, lose the scroll position or empty a multi-selection, which is
 *  exactly what a route table that swapped one whole screen for another would
 *  do.
 */
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import App from "../App";
import LogViewer from "../components/LogViewer";
import SettingsModal from "../components/SettingsModal";
import { useDashboard } from "./context";
import { LISTINGS, LOGS, SETTINGS, withSearch } from "./params";
import PropertyRoute from "./PropertyRoute";

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
        <Route element={<App />}>
          <Route path={LISTINGS} element={null} />
          <Route path={`${LISTINGS}/:id`} element={<PropertyRoute />} />
          <Route path={SETTINGS} element={<SettingsRoute />} />
          <Route path={LOGS} element={<LogsRoute />} />
        </Route>
        <Route path="*" element={<ToListings />} />
      </Routes>
    </BrowserRouter>
  );
}
