/** What the last few scans did, one row per search.
 *
 *  The live panel above only exists while a scan is running, and a user who
 *  walked away during one comes back to a screen that has forgotten it. This is
 *  the part that is still there afterwards: it survives the scan ending and it
 *  survives a reload, because the rows come from the backend rather than from
 *  anything this tab accumulated.
 *
 *  Every word of a row is translated except one. `stopped_because` is the
 *  backend's own sentence and there is no closed vocabulary behind it, so it is
 *  spent where `ProfileHealth` spends `last_run_detail` — only on the runs that
 *  did not simply work, where a rough explanation beats none. `detail` is not
 *  rendered at all: on a successful run the counts have already said it.
 *
 *  Which is exactly why the page cap needs a line of its own here. A search that
 *  stopped at the limit ends `ok` — it worked, it simply did not finish — so
 *  every explanation above skips it, and the counts read as the whole answer.
 *  This is the one row that earns the `incomplete` tone, and it takes the cap
 *  and the portal's own total off the entry rather than out of the copy.
 */
import { formatDateTime, formatNumber, useI18n } from "../../i18n";
import { Limit } from "../../components/Limit";
import { PortalBadge } from "../../components/PortalBadge";
import { useScanJournal } from "../../queries/dashboard";
import { Card, CardHeader, Chip, EmptyState, Skeleton } from "../../ui";
import { Activity } from "../../ui/icons";
import { outcomeLabel, worthExplaining } from "./progress";

export default function ScanJournal() {
  const { t } = useI18n();
  const journal = useScanJournal();
  const entries = journal.data ?? [];

  return (
    <Card asChild className="space-y-3">
      <section aria-labelledby="journal-heading">
        <CardHeader title={<h2 id="journal-heading" className="text-base">{t("activity.journalTitle")}</h2>} />

        {journal.isPending ? (
          <Skeleton lines={3} label={t("activity.loading")} />
        ) : entries.length === 0 ? (
          <EmptyState icon={<Activity size={28} />}
            title={t("activity.journalEmpty")}
            description={t("activity.journalEmptyHint")} />
        ) : (
          // An ordered list because the order is the content: newest first, and
          // a reader working backwards through a scan is reading positions.
          <ol className="divide-y divide-line">
            {entries.map((entry, i) => {
              const outcome = outcomeLabel(entry.outcome);
              return (
                <li key={`${entry.started_at}-${entry.portal}-${i}`} className="py-2.5 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip tone={outcome.tone} dot>{t(outcome.label)}</Chip>
                    <span className="text-sm t-strong">{entry.profile}</span>
                    {entry.portal && <PortalBadge portal={entry.portal} />}
                    {entry.finished_at && (
                      <time dateTime={entry.finished_at} className="ml-auto text-xs t-muted">
                        {formatDateTime(entry.finished_at)}
                      </time>
                    )}
                  </div>
                  <p className="text-xs t-muted">
                    {t("activity.entryCounts", {
                      pages: formatNumber(entry.pages),
                      listings: formatNumber(entry.listings),
                    })}
                    {" · "}
                    {t(entry.mode === "quick" ? "activity.modeQuick" : "activity.modeFull")}
                    {entry.transport && ` · ${entry.transport}`}
                  </p>
                  {worthExplaining(entry.outcome) && entry.stopped_because && (
                    <p className="text-xs t-muted">
                      {t("activity.stoppedBecause", { reason: entry.stopped_because })}
                    </p>
                  )}
                  {/* The other half of "the answer is incomplete": the portal
                      refused this search, so its listings are simply missing
                      rather than absent. Said per portal, which is what the row
                      already is. */}
                  {entry.outcome === "blocked" && (
                    <Limit id="scan.portalBlocked" tone="incomplete">
                      {t("limits.portalBlocked")}
                    </Limit>
                  )}
                  {entry.truncated && (
                    <Limit id="scan.pageCap" tone="incomplete">
                      {entry.total_listings === null
                        ? t("limits.pageCap", { pages: formatNumber(entry.page_limit) })
                        : t("limits.pageCapOfTotal", {
                            pages: formatNumber(entry.page_limit),
                            total: formatNumber(entry.total_listings),
                          })}
                    </Limit>
                  )}
                  {entry.outside_area > 0 && (
                    <Limit id="scan.outsideArea">
                      {t("limits.outsideArea", { count: formatNumber(entry.outside_area) })}
                    </Limit>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </Card>
  );
}
