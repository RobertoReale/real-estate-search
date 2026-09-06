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
 *  is not looking at the grid. The guided first run is beside them for the same
 *  reason, with one difference: it is also where "/" leads on an install that
 *  has never held a search.
 */
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import App from "../App";
import LogViewer from "../components/LogViewer";
import SettingsModal from "../components/SettingsModal";
import AppShell from "../ui/AppShell";
import { ActivityRoute } from "./activity";
import { useDashboard } from "./context";
import InsightsRoute from "./insights/InsightsRoute";
import { OnboardingRoute, shouldGuide } from "./onboarding";
import {
  ACTIVITY, INSIGHTS, LISTINGS, LOGS, ONBOARDING, SEARCHES, SETTINGS, SETUP, withSearch,
} from "./params";
import PropertyRoute from "./property/PropertyRoute";
import { useProfiles } from "../queries/dashboard";
import { SearchesRoute } from "./searches";
import { SetupRoute } from "./setup";

function SettingsRoute() {
  return <SettingsModal onClose={useDashboard().close} />;
}

function LogsRoute() {
  return <LogViewer onClose={useDashboard().close} />;
}

/** Anything nobody recognises. The filters are carried across, because the one
 *  address a person is most likely to type by hand is the bare one, and arriving
 *  at a grid that has quietly dropped what the link asked for is worse than a
 *  404. */
function ToListings() {
  return <Navigate to={withSearch(LISTINGS, useLocation().search)} replace />;
}

/** "/", which is one of two places depending on whether this install has ever
 *  had a search.
 *
 *  A fresh database opening on the listings is a grid with nothing in it and no
 *  filter that would help — the screen is empty because the app has not been
 *  set up, and the set-up is somewhere else. So the first visit opens the guide
 *  instead, and only the first: `shouldGuide` also honours a user who left it.
 *
 *  Nothing is rendered while the profiles are still being fetched. Redirecting
 *  on an empty cache would send every reload to the guide for as long as the
 *  request takes and then, a beat later, snap back — a flash the user reads as
 *  the app not knowing where it is. */
function FirstDestination() {
  const profiles = useProfiles();
  const { search } = useLocation();

  if (profiles.isPending) return null;
  const to = shouldGuide((profiles.data ?? []).length > 0) ? ONBOARDING : LISTINGS;
  return <Navigate to={withSearch(to, search)} replace />;
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
          {/* Beside the grid rather than inside it: someone watching a scan is
              watching the scan, and the journal has to be readable when nothing
              is running. The log stays under `App` — it draws itself as an
              overlay over the grid, and moving it out would leave a blank page
              behind it. */}
          <Route path={ACTIVITY} element={<ActivityRoute />} />
          {/* Inside the shell, so a user who lands here still has the
              navigation and can leave without finishing. The capability setup
              is beside it for the same reason and one more: it is reached from
              Settings as often as from the guide, so it cannot be a screen that
              only exists on the way through. */}
          <Route path={ONBOARDING} element={<OnboardingRoute />} />
          <Route path={SETUP} element={<SetupRoute />} />
          <Route path="/" element={<FirstDestination />} />
        </Route>
        <Route path="*" element={<ToListings />} />
      </Routes>
    </BrowserRouter>
  );
}
