/** What the portals answered when this search was tried, transport by
 *  transport.
 *
 *  The health chip beside a row says *that* a search is blocked. This says
 *  *where*: the ladder has four free rungs and they fail for entirely different
 *  reasons — a direct request refused at the edge, a saved cookie gone stale, a
 *  provider key that was never filled in — and until now telling them apart
 *  meant reading a log file. One line per rung, a mark, the reason in words, and
 *  underneath, the one thing to go and do.
 *
 *  `diagnosis.ts` owns the code→wording tables; this file owns only the shape.
 */

import { useT } from "../../i18n";
import { Chip, Skeleton } from "../../ui";
import { Crashed, Success } from "../../ui/icons";
import { adviceOf, markOf, reasonOf, rungFamily } from "./diagnosis";
import type { Diagnosis } from "../../types";

interface Props {
  /** One run per portal in the box, in the order they were asked. Partial while
   *  a merged search is still being worked through. */
  runs: Diagnosis[];
  pending: boolean;
  /** The backend's own sentence when it refused — the wait after a diagnosis a
   *  minute ago, or the scan already using this connection. */
  error: string;
  /** True only when the box covers more than one portal, where "which portal"
   *  is the answer rather than a heading nobody needs. */
  showPortal: boolean;
}

function Mark({ mark }: { mark: ReturnType<typeof markOf> }) {
  if (mark === "ok") return <Success size={14} className="shrink-0 text-positive-ink" />;
  if (mark === "bad") return <Crashed size={14} className="shrink-0 text-negative-ink" />;
  // Neither tick nor cross: the rung was never asked. A dash says that without
  // pretending it is a third outcome of a request that never happened.
  return <span aria-hidden="true" className="shrink-0 w-3.5 text-center t-dim">–</span>;
}

function Run({ run, showPortal }: { run: Diagnosis; showPortal: boolean }) {
  const t = useT();
  const advice = adviceOf(run.advice);
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {showPortal && (
          <span className="text-2xs font-semibold uppercase t-muted">{run.portal}</span>
        )}
        <Chip tone={advice.tone} dot>
          {t(advice.label, { rung: run.winner })}
        </Chip>
      </div>
      <ul className="space-y-1">
        {run.rungs.map((rung, i) => (
          <li key={rung.rung + "-" + i} className="flex items-start gap-2 text-xs">
            <Mark mark={markOf(rung.outcome)} />
            <span className="font-mono text-2xs t-muted shrink-0 w-32 truncate" title={rung.rung}>
              {rung.rung}
            </span>
            <span className="t-dim shrink-0 w-28 truncate">{t(rungFamily(rung.rung))}</span>
            <span className="min-w-0 flex-1 break-words">
              {t(reasonOf(rung.reason), {
                status: rung.status ?? "—",
                count: rung.listings,
                credits: rung.credits ?? 0,
              })}
              {/* Only where no code covered the case: the harness's own English,
                  which is worse than a translation and better than a blank. */}
              {rung.reason === "skipped" && rung.detail && (
                <span className="t-dim"> — {rung.detail}</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {advice.next && <p className="text-xs t-dim">{t(advice.next)}</p>}
    </div>
  );
}

export default function ProfileDiagnosis({ runs, pending, error, showPortal }: Props) {
  const t = useT();
  return (
    <div data-testid="profile-diagnosis"
      className="w-full mt-1 rounded-lg border border-line p-3 space-y-3">
      <p className="text-xs font-semibold">{t("diagnose.title")}</p>
      {runs.map((run) => (
        <Run key={run.profile_id} run={run} showPortal={showPortal} />
      ))}
      {pending && (
        <div className="space-y-1.5">
          {/* The ladder waits several seconds between requests on purpose, so
              this is a slow panel by design and has to say so — an empty box for
              half a minute reads as a button that did nothing. */}
          <p className="text-xs t-dim">{t("diagnose.running")}</p>
          <Skeleton className="h-3 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      )}
      {error && <p className="text-xs text-negative-ink">{error}</p>}
    </div>
  );
}
