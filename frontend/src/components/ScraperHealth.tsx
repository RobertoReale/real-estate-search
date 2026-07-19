import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";
import type { ScraperHealth, ScraperHealthDay } from "../types";

/** Scraper Health panel (plan-resilience B.5): the anti-bot pipeline degrades
 *  silently — a blocked scraper looks exactly like a quiet market — so this
 *  panel turns the persisted per-portal daily counts into a visible trend:
 *  block-rate per portal, the transport that carried the last scan, and the
 *  live failure streaks. Dependency-free like PriceTrends. */

interface DayCell {
  day: ScraperHealthDay;
  /** status color class for the day: all-good / partial / all-failed */
  cls: string;
  label: string;
}

function dayCells(days: ScraperHealthDay[]): DayCell[] {
  return days.map((day) => {
    const failures = day.blocked + day.errors;
    let cls = "bg-emerald-500/80";
    let state = "all scans ok";
    if (day.attempts === 0) {
      cls = "bg-slate-300 dark:bg-slate-700";
      state = "no scans";
    } else if (failures === day.attempts) {
      cls = "bg-rose-500/90";
      state = "every scan failed";
    } else if (failures > 0) {
      cls = "bg-amber-400/90";
      state = "some scans failed";
    }
    return {
      day,
      cls,
      label:
        `${day.date}: ${state} — ${day.attempts} scans, ` +
        `${day.blocked} blocked, ${day.errors} errors`,
    };
  });
}

export default function ScraperHealthPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ScraperHealth | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadSeq = useRef(0);
  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    setLoading(true);
    try {
      const res = await api.getScraperHealth();
      if (seq !== loadSeq.current) return;
      setData(res);
      setError("");
    } catch (e) {
      if (seq !== loadSeq.current) return;
      setError(e instanceof Error ? e.message : "Could not load scraper health");
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }, []);

  // fetched only while open, like MarketVelocity: an aggregate query the
  // dashboard does not need while the panel is collapsed
  useEffect(() => {
    if (!open) return;
    load();
  }, [open, load]);

  const failingProfiles = data?.profiles.filter((p) => p.consecutive_failures > 0) ?? [];
  const empty = data && data.portals.length === 0;

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <button
        className="w-full flex flex-wrap items-center justify-between gap-2 text-left"
        onClick={() => setOpen(!open)}>
        <h2 className="font-semibold text-base">
          🩺 Scraper health{" "}
          <span className="t-muted text-sm font-normal">
            is the anti-bot pipeline still getting through?
          </span>
        </h2>
        <span className="t-muted text-sm">{open ? "Hide ▲" : "Show ▼"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-5">
          {loading && !data && <p className="text-sm t-muted">Loading…</p>}
          {error && <p className="accent-bad text-sm">⚠️ {error}</p>}

          {data && (
            <p className="text-xs t-muted">
              Last {data.window_days} days of scan outcomes per portal. Next scan
              starts on: <span className="t-strong">{data.transport}</span>.
            </p>
          )}

          {empty && (
            <div className="panel rounded-xl p-6 text-center text-sm t-muted">
              <p className="text-2xl mb-2">🩺</p>
              No scans recorded yet — this fills in as scans run.
            </div>
          )}

          {data && data.portals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="t-muted text-xs text-left">
                  <tr className="border-b border-slate-200 dark:border-slate-700/50">
                    <th className="py-2 pr-3 font-medium">Portal</th>
                    <th className="py-2 px-3 font-medium">Days (oldest → today)</th>
                    <th className="py-2 px-3 font-medium text-right">Scans</th>
                    <th
                      className="py-2 px-3 font-medium text-right"
                      title="Share of scans that came back blocked or in error over the window">
                      Failure rate
                    </th>
                    <th className="py-2 pl-3 font-medium">Last transport</th>
                  </tr>
                </thead>
                <tbody>
                  {data.portals.map((p) => (
                    <tr
                      key={p.portal}
                      className="border-b border-slate-100 dark:border-slate-800/50">
                      <td className="py-2 pr-3 t-strong capitalize">{p.portal}</td>
                      <td className="py-2 px-3">
                        <div className="flex items-end gap-[2px]" aria-hidden={false}>
                          {dayCells(p.days).map((c) => (
                            <span
                              key={c.day.date}
                              title={c.label}
                              className={`inline-block w-2.5 h-4 rounded-[3px] ${c.cls}`}
                            />
                          ))}
                        </div>
                      </td>
                      <td className="py-2 px-3 text-right t-body">{p.attempts}</td>
                      <td
                        className={`py-2 px-3 text-right font-medium ${
                          p.block_rate >= 0.5
                            ? "accent-bad"
                            : p.block_rate > 0
                              ? "text-amber-600 dark:text-amber-400"
                              : "accent-good"
                        }`}>
                        {(p.block_rate * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 pl-3 t-body">{p.last_transport || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs t-dim mt-2">
                Green day = every scan ok · amber = some failed · red = all
                failed. Hover a day for the exact counts.
              </p>
            </div>
          )}

          {failingProfiles.length > 0 && (
            <div>
              <h3 className="font-medium text-sm mb-2">Searches currently failing</h3>
              <ul className="text-sm space-y-1">
                {failingProfiles.map((p) => (
                  <li key={p.profile_id} className="flex items-center gap-2">
                    <span className="accent-bad">●</span>
                    <span className="t-strong">{p.name}</span>
                    <span className="t-muted">
                      ({p.portal}) — {p.consecutive_failures} consecutive{" "}
                      {p.last_run_status || "failed"} scans
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-xs t-dim mt-2">
                A short streak is routine (transient anti-bot blocks). A long one
                means the free path is down: consider a proxy pool or a
                scrape-API key in Settings.
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
