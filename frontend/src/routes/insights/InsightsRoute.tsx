/** What the collected properties add up to: are the scrapers still working, how
 *  fast the market is moving, and where prices are going.
 *
 *  These three panels used to sit above the grid, collapsed, and pushed the
 *  first property card 1385px down a 900px screen — a user with data had to
 *  scroll past the analysis to reach the thing the analysis is about. They are a
 *  place of their own now, and the grid is what the app opens on.
 *
 *  **Nothing here is behind a disclosure any more.** Three collapsed headers
 *  were the right shape when this was the top of somebody else's screen and the
 *  wrong one the moment it became a destination: a page whose whole content is
 *  three "Show" links is a page that asks to be clicked three times before it
 *  says anything. They are sections now, and the panels under `insights/` are
 *  the sections rather than reusable components — a market-velocity table knows
 *  what a contract is, and no second screen should want one.
 *
 *  The contract and the city come from the query string, which is the same
 *  source the grid reads them from, so the two screens are looking at the same
 *  market and a link carries which one.
 */
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";

import MarketVelocityPanel from "./MarketVelocity";
import PriceTrends from "./PriceTrends";
import ScraperHealthPanel from "./ScraperHealth";
import { useT } from "../../i18n";
import { useProfiles } from "../../queries/dashboard";
import { Button, Card, EmptyState } from "../../ui";
import { ICON_SIZE, Insights, Searches } from "../../ui/icons";
import { filtersFromSearch, propertyPath, SEARCHES, withSearch } from "../params";

export default function InsightsRoute() {
  const t = useT();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const filters = filtersFromSearch(params);
  const profiles = useProfiles().data ?? [];

  // Every panel here is an aggregate over what the scans collected. With no
  // search saved there is nothing to aggregate, and three panels each saying so
  // separately is three ways of reporting the same absence.
  if (profiles.length === 0) {
    return (
      <Card padding="none">
        <EmptyState headingLevel={2}
          icon={<Insights size={ICON_SIZE.display} strokeWidth={1.25} />}
          title={t("insights.empty")}
          description={t("insights.emptyHint")}
          action={
            <Button asChild variant="solid" tone="accent">
              <NavLink data-action="insights.toSearches" to={withSearch(SEARCHES, params.toString())}>
                <Searches /> {t("app.addSearch")}
              </NavLink>
            </Button>
          } />
      </Card>
    );
  }

  return (
    <>
      <ScraperHealthPanel />
      <MarketVelocityPanel contract={filters.contract} city={filters.city} />
      {/* A comparable listing opens where every property opens — on the grid,
          with the detail over it — so there is one property screen rather than
          one per place a property can be named from. */}
      <PriceTrends contract={filters.contract} city={filters.city}
        onOpenProperty={(p) => navigate(withSearch(propertyPath(p.id), params.toString()))} />
    </>
  );
}
