import { useScraperHealth } from "../../queries/insights";
import DayStrip from "./DayStrip";
import { translateCurrent, useT } from "../../i18n";
import { Card, cx, EmptyState, FOCUS_RING } from "../../ui";
import { Dot, Health, ICON_SIZE, Warning } from "../../ui/icons";

/** Scraper Health: the anti-bot pipeline degrades silently — a blocked scraper
 *  looks exactly like a quiet market — so this section turns the persisted
 *  per-portal daily counts into a visible trend: block-rate per portal, the
 *  transport that carried the last scan, and the live failure streaks. */

export default function ScraperHealthPanel() {
  const t = useT();
  const { data, isError, error, isPending } = useScraperHealth();
  const message = isError
    ? (error instanceof Error ? error.message : translateCurrent("health.loadFailed"))
    : "";

  const failingProfiles = data?.profiles.filter((p) => p.consecutive_failures > 0) ?? [];
  const empty = data && data.portals.length === 0;

  return (
    <Card asChild padding="lg">
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="flex items-center gap-1.5 font-semibold text-base">
            <Health className="shrink-0" />
            {t("health.title")}
          </h2>
          <p className="t-muted text-sm">{t("health.subtitle")}</p>
        </div>

        <div className="mt-4 space-y-5">
          {isPending && !data && <p className="text-sm t-muted">{t("common.loading")}</p>}
          {message && <p className="accent-bad text-sm inline-flex items-center gap-1.5"><Warning /> {message}</p>}

          {data && (
            <p className="text-xs t-muted">
              {t("health.window", {
                days: data.window_days,
                transport: data.transport,
              })}
            </p>
          )}

          {empty && (
            <EmptyState className="panel rounded-xl"
              icon={<Health size={ICON_SIZE.display} strokeWidth={1.25} />}
              title={t("health.empty")} />
          )}

          {/* A region that scrolls has to be focusable, or a phone-width reader
              can see that the table runs off the edge and have no way to follow
              it: a mouse wheel is not an input everybody has. */}
          {data && data.portals.length > 0 && (
            <div className={cx("overflow-x-auto rounded-sm", FOCUS_RING)} tabIndex={0}
              role="region" aria-label={t("health.historyTitle")}>
              {/* Labelled as history explicitly, and the streak below as the
                  live state. The two are different kinds of number sitting on
                  the same panel: a day's `blocked` count is a total that stays
                  on the record for ever, while a streak is what is true right
                  now and clears on the next scan that gets through. Unlabelled,
                  a historical total reads as a current problem. */}
              <h3 className="font-medium text-sm mb-2">{t("health.historyTitle")}</h3>
              <table className="w-full text-sm">
                <thead className="t-muted text-xs text-left">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3 font-medium">{t("health.colPortal")}</th>
                    <th className="py-2 px-3 font-medium">{t("health.colDays")}</th>
                    <th className="py-2 px-3 font-medium text-right">{t("health.colScans")}</th>
                    <th
                      className="py-2 px-3 font-medium text-right"
                      title={t("health.colFailureRateTitle")}>
                      {t("health.colFailureRate")}
                    </th>
                    <th className="py-2 pl-3 font-medium">{t("health.colTransport")}</th>
                  </tr>
                </thead>
                <tbody className="tnum">
                  {data.portals.map((p) => (
                    <tr
                      key={p.portal}
                      className="border-b border-line-subtle">
                      <td className="py-2 pr-3 t-strong capitalize">{p.portal}</td>
                      <td className="py-2 px-3">
                        <DayStrip days={p.days} />
                      </td>
                      <td className="py-2 px-3 text-right t-body">{p.attempts}</td>
                      <td
                        className={`py-2 px-3 text-right font-medium ${
                          p.block_rate >= 0.5
                            ? "accent-bad"
                            : p.block_rate > 0
                              ? "text-caution-ink"
                              : "accent-good"
                        }`}>
                        {(p.block_rate * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 pl-3 t-body">{p.last_transport || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs t-dim mt-2">{t("health.legend")}</p>
            </div>
          )}

          {failingProfiles.length > 0 && (
            <div>
              <h3 className="font-medium text-sm">{t("health.failingTitle")}</h3>
              <p className="text-xs t-dim mb-2">{t("health.failingSubtitle")}</p>
              <ul className="text-sm space-y-1">
                {failingProfiles.map((p) => (
                  <li key={p.profile_id} className="flex items-center gap-2">
                    <span className="accent-bad"><Dot size={10} fill="currentColor" /></span>
                    <span className="t-strong">{p.name}</span>
                    <span className="t-muted">
                      {t("health.failingRow", {
                        portal: p.portal,
                        count: p.consecutive_failures,
                        status: p.last_run_status || t("health.failingStatusFallback"),
                      })}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-xs t-dim mt-2">{t("health.failingHint")}</p>
            </div>
          )}
        </div>
      </section>
    </Card>
  );
}
