/** The searches that go out to the portals: creating them, editing them, and
 *  turning them off.
 *
 *  A place of its own rather than a panel above the grid. It is the screen a
 *  user spends time on twice — once at the start, and again whenever the market
 *  moves — and it was costing every other visit the top of the page.
 *
 *  Three regions, in the order a user needs them: what is wrong with the account
 *  as a whole, then the searches, then the jobs that repair the collection. The
 *  last of those is under a heading that says so out loud, because "Find
 *  coordinates" next to a list of searches reads as something a search does.
 *
 *  After this screen exists, **the listings page holds no configuration control
 *  at all** — every one of them is here or in Settings. `e2e/coverage.spec.ts`
 *  holds that line rather than this comment.
 */
import MaintenanceActions from "../../components/MaintenanceActions";
import SearchProfiles from "../../components/SearchProfiles";
import { useProfiles } from "../../queries/dashboard";
import { useRefreshDashboard } from "../../queries/properties";
import { useSettings } from "../../queries/settings";
import ChannelBanner from "./ChannelBanner";

export default function SearchesRoute() {
  const profiles = useProfiles().data ?? [];
  const settings = useSettings().data ?? null;
  const refresh = useRefreshDashboard();

  return (
    <>
      <ChannelBanner profiles={profiles} settings={settings} />
      <SearchProfiles profiles={profiles} settings={settings} onChanged={refresh} />
      {/* Geocoding the pins and clearing that cache are housekeeping for the
          whole database, not clauses of a query. They sat at the bottom of the
          filter bar, where a user looking for "max price" met "clear the
          geocoding cache" instead; here they are beside the other thing that
          acts on the collection rather than on one search. */}
      <MaintenanceActions />
    </>
  );
}
