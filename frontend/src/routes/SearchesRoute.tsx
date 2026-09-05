/** The searches that go out to the portals: creating them, editing them, and
 *  turning them off.
 *
 *  A place of its own rather than a panel above the grid. It is the screen a
 *  user spends time on twice — once at the start, and again whenever the market
 *  moves — and it was costing every other visit the top of the page.
 */
import MaintenanceActions from "../components/MaintenanceActions";
import SearchProfiles from "../components/SearchProfiles";
import { useProfiles } from "../queries/dashboard";
import { useRefreshDashboard } from "../queries/properties";
import { useSettings } from "../queries/settings";

export default function SearchesRoute() {
  const profiles = useProfiles().data ?? [];
  const settings = useSettings().data ?? null;
  const refresh = useRefreshDashboard();

  return (
    <>
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
