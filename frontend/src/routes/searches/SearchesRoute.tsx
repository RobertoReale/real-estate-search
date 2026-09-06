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
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import MaintenanceActions from "../../components/MaintenanceActions";
import SearchProfiles from "../../components/SearchProfiles";
import { useT } from "../../i18n";
import { useProfiles } from "../../queries/dashboard";
import { useRefreshDashboard } from "../../queries/properties";
import { useSettings } from "../../queries/settings";
import { Button, Card, ErrorState, Skeleton } from "../../ui";
import ChannelBanner from "./ChannelBanner";
import FromFilters from "./FromFilters";
import { readHandoff } from "./handoff";

export default function SearchesRoute() {
  const t = useT();
  const profilesQuery = useProfiles();
  const profiles = profilesQuery.data ?? [];
  const settings = useSettings().data ?? null;
  const refresh = useRefreshDashboard();
  const [params] = useSearchParams();
  // Someone who came here from "Search the portals for this" arrives with the
  // grid's filters on the address. The form opens on what could be carried and
  // the banner above it accounts for the rest.
  const handoff = useMemo(() => readHandoff(params), [params]);

  // Until the searches arrive there is nothing here to be right about: an empty
  // list, a banner about channels for searches that may not exist, and a panel
  // saying no search is configured are all claims made from `data ?? []`. The
  // shape of the list is the only honest thing to show while it is in flight.
  if (profilesQuery.isPending) {
    return (
      <Card padding="lg">
        <Skeleton className="h-4 w-1/3" label={t("common.loading")} />
        <Skeleton className="mt-5 h-32 w-full" />
      </Card>
    );
  }

  // The searches are the screen. Without them the maintenance jobs below would
  // be all that is left, which reads as a page that has loaded and has nothing
  // on it rather than as a page that could not be loaded.
  if (profilesQuery.isError) {
    return (
      <Card padding="none">
        <ErrorState headingLevel={2}
          title={t("profiles.loadFailed")}
          description={
            profilesQuery.error instanceof Error ? profilesQuery.error.message : ""
          }
          action={(
            <Button data-action="profiles.loadError.retry" variant="solid" tone="accent"
              aria-busy={profilesQuery.isFetching}
              onClick={() => { void profilesQuery.refetch(); }}>
              {profilesQuery.isFetching ? t("common.loading") : t("common.retry")}
            </Button>
          )} />
      </Card>
    );
  }

  return (
    <>
      <ChannelBanner profiles={profiles} settings={settings} />
      {handoff && <FromFilters handoff={handoff} profiles={profiles} />}
      {/* Keyed on the handover so arriving with one opens the form on it: the
          prefill is the form's initial state, and initial state is only read
          once. */}
      <SearchProfiles key={handoff ? "from-filters" : "plain"}
        profiles={profiles} settings={settings} onChanged={refresh}
        prefill={handoff?.params ?? null} />
      {/* Geocoding the pins and clearing that cache are housekeeping for the
          whole database, not clauses of a query. They sat at the bottom of the
          filter bar, where a user looking for "max price" met "clear the
          geocoding cache" instead; here they are beside the other thing that
          acts on the collection rather than on one search. */}
      <MaintenanceActions />
    </>
  );
}
