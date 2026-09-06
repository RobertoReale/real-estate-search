/** The results region with nothing in it — in its three quite different meanings.
 *
 *  "No listings" is several situations wearing one appearance, and they need
 *  opposite answers. Telling them apart is the whole job of this file.
 *
 *  - **A database that has never held a search.** There is nothing to loosen,
 *    and every control on this screen operates on properties that do not exist
 *    yet. It used to be answered here with a numbered list of three things to go
 *    and do elsewhere — documentation, printed on the one screen whose emptiness
 *    it is supposed to fix. It is the guided run now (`routes/onboarding/`), and
 *    what is left here is the sentence and the control that starts it.
 *  - **Searches exist, but nothing has come back yet.** Nothing is wrong and
 *    nothing needs setting up: the next scan is the answer.
 *  - **Listings were collected and none of them match.** This is the one that
 *    misleads, and it is the reason the count is in the sentence. "No properties
 *    match" reads as *there are no such houses* — a claim about the market, made
 *    by a filter that only ever looked at this machine. So it names how many it
 *    looked at, and offers the thing that would actually answer the question:
 *    the same criteria, sent out to the portals as a search. What survives that
 *    translation and what does not is `routes/searches/handoff.ts`, which is
 *    where the honesty about it lives.
 */
import { NavLink } from "react-router-dom";

import { useT } from "../../i18n";
import type { PropertyFilters } from "../../types";
import { Button, Card, EmptyState } from "../../ui";
import { ICON_SIZE, NoResults, Searches } from "../../ui/icons";
import { handoffPath } from "../searches/handoff";
import { ONBOARDING, withSearch } from "../params";

interface Props {
  /** Whether a monitored search exists at all. */
  hasProfiles: boolean;
  /** How many listings this machine holds in this market, whatever the filters
   *  say — the set these filters found nothing in. */
  collected: number;
  /** What the user is asking for, to carry over to the portals. */
  filters: PropertyFilters;
  /** The current query string. Carried onto the guide so that finishing it
   *  comes back to the filters the user arrived with. */
  search: string;
}

export default function EmptyResults({ hasProfiles, collected, filters, search }: Props) {
  const t = useT();

  if (collected > 0) {
    return (
      <Card padding="none">
        <EmptyState headingLevel={2}
          icon={<NoResults size={ICON_SIZE.display} strokeWidth={1.25} />}
          title={t("app.noMatches")}
          description={t("app.noMatchesHint", { count: collected })}
          action={(
            <Button asChild variant="solid" tone="accent">
              <NavLink data-action="app.toPortals" to={handoffPath(filters)}>
                <Searches /> {t("app.toPortals")}
              </NavLink>
            </Button>
          )} />
      </Card>
    );
  }

  return (
    <Card padding="none">
      <EmptyState headingLevel={2}
        icon={<NoResults size={ICON_SIZE.display} strokeWidth={1.25} />}
        title={t("app.welcome")}
        description={hasProfiles ? t("app.collectedNoneHint") : t("app.welcomeHint")}
        action={hasProfiles ? undefined : (
          <Button asChild variant="solid" tone="accent">
            <NavLink data-action="app.addSearch" to={withSearch(ONBOARDING, search)}>
              <Searches /> {t("app.addSearch")}
            </NavLink>
          </Button>
        )} />
    </Card>
  );
}
