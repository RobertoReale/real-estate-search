/** The results region with nothing in it — in its two quite different meanings.
 *
 *  "No listings" is two situations wearing one appearance, and they need
 *  opposite answers. Filters that match nothing: the way out is to loosen them,
 *  and the rail beside this is already the way to do it. A database that has
 *  never held a search: there is nothing to loosen, and every control on this
 *  screen operates on properties that do not exist yet. Telling the two apart is
 *  the whole job of this file.
 *
 *  The second case used to be answered here with a numbered list of three
 *  things to go and do elsewhere — which is documentation, printed on the one
 *  screen whose emptiness it is supposed to fix. It is the guided run now
 *  (`routes/onboarding/`), and what is left here is the sentence that says why
 *  the page is empty and the control that starts the guide.
 */
import { NavLink } from "react-router-dom";

import { useT } from "../../i18n";
import { Button, Card, EmptyState } from "../../ui";
import { ICON_SIZE, NoResults, Searches } from "../../ui/icons";
import { ONBOARDING, withSearch } from "../params";

interface Props {
  /** Whether a monitored search exists at all: the one fact that separates
   *  "nothing matches" from "nothing has ever been collected". */
  hasProfiles: boolean;
  /** The current query string. Carried onto the guide so that finishing it
   *  comes back to the filters the user arrived with. */
  search: string;
}

export default function EmptyResults({ hasProfiles, search }: Props) {
  const t = useT();

  return (
    <Card padding="none">
      <EmptyState headingLevel={2}
        icon={<NoResults size={ICON_SIZE.display} strokeWidth={1.25} />}
        title={hasProfiles ? t("app.noMatches") : t("app.welcome")}
        description={hasProfiles ? t("app.noMatchesHint") : t("app.welcomeHint")}
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
