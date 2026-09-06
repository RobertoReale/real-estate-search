/** The scan, while it runs and after it has finished.
 *
 *  Reached from the header rather than from the navigation — see `routes/params`
 *  for why that is a decision about width. What it replaced there was the button
 *  that opened the backend log, and that is the point of the third section: the
 *  log is a good tool for the question "what did the process do", and it had
 *  been standing in for "are my searches working?" purely because nothing else
 *  was offered. It keeps its place, one press further in, under a heading that
 *  says what it is for.
 */
import { useLocation, NavLink } from "react-router-dom";

import { useI18n } from "../../i18n";
import { Button, Card, CardHeader } from "../../ui";
import { Logs } from "../../ui/icons";
import { LOGS, withSearch } from "../params";
import ScanJournal from "./ScanJournal";
import ScanLive from "./ScanLive";

export default function ActivityRoute() {
  const { t } = useI18n();
  const { search } = useLocation();

  return (
    <>
      <ScanLive />
      <ScanJournal />
      <Card asChild className="space-y-3">
        <section aria-labelledby="diagnostics-heading">
          <CardHeader
            title={
              <h2 id="diagnostics-heading" className="text-base">
                {t("activity.diagnostics")}
              </h2>
            }
            actions={
              <Button asChild>
                <NavLink data-action="activity.openLog" to={withSearch(LOGS, search)}>
                  <Logs size={18} /> {t("activity.openLog")}
                </NavLink>
              </Button>
            } />
          <p className="text-xs leading-relaxed t-muted">{t("activity.diagnosticsBody")}</p>
        </section>
      </Card>
    </>
  );
}
