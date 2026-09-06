/** What the scanner is doing, while it is doing it.
 *
 *  A scan is minutes long, most of it spent deliberately idle between page
 *  requests, and until this screen existed the whole account of it was the word
 *  "scanning" on one line of the header. The other thing on offer was the
 *  backend log, which answers "what did the process do" and not "are my
 *  searches working?".
 *
 *  So every fact here is one the user asked for by saving a search: which
 *  search of how many, on which portal, how far into it, how much has come
 *  back, over what transport — and, when nothing is moving, that nothing is
 *  moving *on purpose*. The pause is the single largest part of a scan's
 *  running time and the one a user reads as a crash, so it is named rather than
 *  hidden behind a spinner.
 *
 *  **No proportion without a total.** `pageProportion` decides that, once; see
 *  `progress.ts` for why it is a rule rather than a formatting choice.
 *
 *  **A lost stream is not a finished scan.** The status here is the same query
 *  the header reads, so when the stream cannot be opened it goes back to
 *  polling on its own (B.4) and everything below keeps moving. The one thing
 *  this adds is saying so, because a screen that silently changes where its
 *  numbers come from is a screen nobody can debug.
 */
import { formatDateTime, useI18n } from "../../i18n";
import { PortalBadge } from "../../components/PortalBadge";
import { ProgressBar } from "../../components/ProgressBar";
import { useToasts } from "../../components/Toast";
import { useScanStatus, useTriggerScan } from "../../queries/dashboard";
import { usePollingFallback } from "../../queries/events";
import { Button, Card, CardHeader, Chip, Skeleton } from "../../ui";
import { Note, Paused, Run, Scheduled } from "../../ui/icons";
import { pageProportion, phaseLabel } from "./progress";

export default function ScanLive() {
  const { t } = useI18n();
  const toasts = useToasts();
  const status = useScanStatus();
  const triggerScan = useTriggerScan();
  const streamDown = usePollingFallback();

  const data = status.data ?? null;
  const running = data?.running ?? false;
  const progress = data?.progress ?? null;
  const pages = pageProportion(progress);

  function scanNow() {
    triggerScan.mutate(undefined, {
      onError: (e) => toasts.fail(e, { doing: t("toast.scanFailed"), retry: scanNow }),
    });
  }

  return (
    <Card className="space-y-4">
      <CardHeader
        title={
          <h2 className="text-base">
            {running ? t("activity.liveTitle") : t("activity.idleTitle")}
          </h2>
        }
        actions={
          // The header carries the same action, and this is not a duplicate by
          // accident: a user who came here to watch a scan and found none
          // running should not have to work out that the way to start one is
          // the button above the navigation.
          <Button data-action="activity.scan" variant="solid" tone="accent"
            onClick={scanNow} disabled={running}>
            <Run /> {running ? t("nav.running") : t("activity.start")}
          </Button>
        } />

      {status.isPending ? (
        // Not "no scan running": with nothing fetched yet that is a guess, and
        // it is the guess that makes a running scan look finished.
        <Skeleton className="h-16 w-full" label={t("activity.loading")} />
      ) : running ? (
        <div className="space-y-3 text-sm">
          {/* Which search, and where. Changes once per search rather than per
              frame, so it sits outside the live region below — a name that is
              re-announced every time a page number moves is noise. */}
          {progress?.profile && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="t-strong">{progress.profile}</span>
              {progress.portal && <PortalBadge portal={progress.portal} />}
              {progress.profile_total > 0 && (
                <span className="t-muted text-xs">
                  {t("activity.searchOf", {
                    index: progress.profile_index, total: progress.profile_total,
                  })}
                </span>
              )}
            </div>
          )}

          <div role="status" className="space-y-1">
            <p className="t-strong">
              {t(phaseLabel(progress?.phase ?? ""), {
                page: progress?.page ?? 0,
                seconds: Math.round(progress?.waiting_seconds ?? 0),
              })}
            </p>
            <p className="t-muted">
              {progress?.total_listings
                ? t("activity.foundOf", {
                    count: progress.listings, total: progress.total_listings,
                  })
                : t("activity.found", { count: progress?.listings ?? 0 })}
            </p>
            {progress?.transport && (
              <p className="flex items-center gap-1.5 t-muted text-xs">
                {t("activity.transport")}
                {/* Its own chip rather than a word in the sentence: the ladder
                    escalates mid-scan, and the point of showing the transport
                    at all is that the change is visible when it happens. */}
                <Chip tone="info" size="sm">{progress.transport}</Chip>
              </p>
            )}
          </div>

          {pages ? (
            <ProgressBar label={t("activity.pagesLabel")}
              done={pages.done} total={pages.total}>
              {t("activity.pageOf", { done: pages.done, total: pages.total })}
            </ProgressBar>
          ) : (
            <ProgressBar label={t("activity.pagesLabel")} indeterminate>
              {t("activity.pageCount", { page: progress?.page ?? 0 })} ·{" "}
              {t("activity.pagesUnknown")}
            </ProgressBar>
          )}

          {progress?.phase === "waiting" && (
            <p className="flex items-start gap-2 text-xs leading-relaxed t-muted">
              <Note className="mt-0.5 shrink-0" />
              {t("activity.waitingWhy")}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-1 text-sm t-muted">
          <p>{t("activity.idleBody")}</p>
          {data?.last_finished_at && (
            <p>{t("activity.lastFinished", { time: formatDateTime(data.last_finished_at) })}</p>
          )}
          {data?.paused ? (
            <p className="flex items-center gap-1.5"><Paused /> {t("activity.paused")}</p>
          ) : data?.next_auto_run ? (
            <p className="flex items-center gap-1.5">
              <Scheduled /> {t("activity.nextScan", {
                time: formatDateTime(data.next_auto_run),
              })}
            </p>
          ) : null}
        </div>
      )}

      {streamDown && (
        <p className="flex items-start gap-2 text-xs leading-relaxed t-muted">
          <Note className="mt-0.5 shrink-0" />
          {t("activity.streamDown")}
        </p>
      )}
    </Card>
  );
}
