import { useCallback, useEffect, useRef, useState } from "react";
import { formatDate, translateCurrent, useT } from "../i18n";
import { api } from "../services/api";
import type { MarketVelocity as Velocity } from "../types";

interface Props {
  contract: "sale" | "rent";
  city: string;
}

const fmtDays = (value: number | null) =>
  value === null ? "—" : `${Math.round(value)}d`;

/** Signed delta vs the local median €/sqm: above is a warning, below is not
 *  automatically a bargain, so only the sign is colored. */
function SqmDelta({ value }: { value: number | null }) {
  if (value === null) return <span className="t-dim">—</span>;
  const above = value > 0;
  return (
    <span className={above ? "accent-bad" : "accent-good"}>
      {above ? "+" : ""}
      {value.toFixed(0)}%
    </span>
  );
}

export default function MarketVelocityPanel({ contract, city }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Velocity | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // monotonic id per request (like App.tsx's refreshSeq): `city` updates on
  // every keystroke, and a slow response for "M" landing after the one for
  // "Milano" would repaint the panel with stale statistics
  const loadSeq = useRef(0);
  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    setLoading(true);
    try {
      const res = await api.getMarketVelocity(contract, city);
      if (seq !== loadSeq.current) return;
      setData(res);
      setError("");
    } catch (e) {
      if (seq !== loadSeq.current) return;
      setError(e instanceof Error ? e.message : translateCurrent("velocity.loadFailed"));
    } finally {
      if (seq === loadSeq.current) setLoading(false);
    }
  }, [contract, city]);

  // fetched only while the panel is open: these are aggregate queries over
  // the whole table, and the dashboard already polls every 30 seconds.
  // Debounced like App.tsx's refresh, so typing a city fires one request
  // when the typing pauses instead of one per letter.
  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(load, 250);
    return () => window.clearTimeout(t);
  }, [open, load]);

  const empty = data && data.areas.length === 0 && data.agencies.length === 0;

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <button
        className="w-full flex flex-wrap items-center justify-between gap-2 text-left"
        onClick={() => setOpen(!open)}>
        <h2 className="font-semibold text-base">
          {t("velocity.title")}{" "}
          <span className="t-muted text-sm font-normal">
            {t(contract === "rent" ? "velocity.subtitleRent" : "velocity.subtitleSale")}
          </span>
        </h2>
        <span className="t-muted text-sm">{open ? t("health.hide") : t("health.show")}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-5">
          {loading && !data && <p className="text-sm t-muted">{t("common.loading")}</p>}
          {error && <p className="accent-bad text-sm">⚠️ {error}</p>}

          {data && (
            <p className="text-xs t-muted">
              {t("velocity.tracked", { count: data.total_properties })}
              {city && t("velocity.inCity", { city })}
              {t("velocity.left", { count: data.closed_properties })}
              {data.sold_properties > 0 &&
                t("velocity.confirmedSold", { count: data.sold_properties })}
              {data.tracking_since &&
                t("velocity.observedSince", { date: formatDate(data.tracking_since) })}
              {t("velocity.minSample", { count: data.min_sample })}
            </p>
          )}

          {empty && (
            <div className="panel rounded-xl p-6 text-center text-sm t-muted">
              <p className="text-2xl mb-2">⏳</p>
              {t("velocity.empty", { count: data?.min_sample ?? 0 })}
            </div>
          )}

          {data && data.areas.length > 0 && (
            <div>
              <h3 className="font-medium text-sm mb-2">
                {t("velocity.areasTitle")}{" "}
                <span className="t-muted font-normal">{t("velocity.areasHint")}</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="t-muted text-xs text-left">
                    <tr className="border-b border-slate-200 dark:border-slate-700/50">
                      <th className="py-2 pr-3 font-medium">{t("velocity.colArea")}</th>
                      <th className="py-2 px-3 font-medium text-right">{t("velocity.colTracked")}</th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colDaysToExitTitle")}>
                        {t("velocity.colDaysToExit")}
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colStillListedTitle")}>
                        {t("velocity.colStillListed")}
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colLeftMarketTitle")}>
                        {t("velocity.colLeftMarket")}
                      </th>
                      <th className="py-2 pl-3 font-medium text-right"
                        title={t("velocity.colCutPriceTitle")}>
                        {t("velocity.colCutPrice")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.areas.map((a) => (
                      <tr key={`${a.scope}-${a.city}-${a.zone}`}
                        className="border-b border-slate-100 dark:border-slate-800/50">
                        <td className="py-2 pr-3">
                          <span className="t-strong">{a.zone || a.city}</span>
                          {a.scope === "city" ? (
                            <span className="ml-2 text-[10px] chip-blue px-1.5 py-0.5 rounded uppercase font-bold">
                              {t("velocity.wholeCity")}
                            </span>
                          ) : (
                            <span className="t-dim text-xs"> · {a.city}</span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right t-body">{a.sample}</td>
                        <td className="py-2 px-3 text-right t-strong font-medium">
                          {fmtDays(a.median_days_to_gone)}
                        </td>
                        <td className="py-2 px-3 text-right t-body">
                          {fmtDays(a.median_days_listed)}
                        </td>
                        <td className="py-2 px-3 text-right t-body">
                          {a.sell_through_pct.toFixed(0)}%
                        </td>
                        <td className="py-2 pl-3 text-right t-body">
                          {a.price_drop_pct.toFixed(0)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {data && data.agencies.length > 0 && (
            <div>
              <h3 className="font-medium text-sm mb-2">
                {t("velocity.agenciesTitle")}{" "}
                <span className="t-muted font-normal">{t("velocity.agenciesHint")}</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="t-muted text-xs text-left">
                    <tr className="border-b border-slate-200 dark:border-slate-700/50">
                      <th className="py-2 pr-3 font-medium">{t("velocity.colAgency")}</th>
                      <th className="py-2 px-3 font-medium text-right">{t("velocity.colListings")}</th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colVsAreaTitle")}>
                        {t("velocity.colVsArea")}
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colAgencyCutTitle")}>
                        {t("velocity.colCutPrice")}
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title={t("velocity.colTypicalCutTitle")}>
                        {t("velocity.colTypicalCut")}
                      </th>
                      <th className="py-2 pl-3 font-medium text-right">
                        {t("velocity.colDaysToExit")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.agencies.map((a) => (
                      <tr key={a.agency}
                        className="border-b border-slate-100 dark:border-slate-800/50">
                        <td className="py-2 pr-3 t-strong truncate max-w-[16rem]"
                          title={a.agency}>
                          {a.agency}
                        </td>
                        <td className="py-2 px-3 text-right t-body">{a.sample}</td>
                        <td className="py-2 px-3 text-right font-medium">
                          <SqmDelta value={a.median_sqm_price_delta_pct} />
                        </td>
                        <td className="py-2 px-3 text-right t-body">
                          {a.price_drop_pct.toFixed(0)}%
                        </td>
                        <td className="py-2 px-3 text-right t-body">
                          {a.median_drop_pct === null
                            ? "—"
                            : `−${a.median_drop_pct.toFixed(0)}%`}
                        </td>
                        <td className="py-2 pl-3 text-right t-body">
                          {fmtDays(a.median_days_to_gone)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* The numbers above are only as honest as their caveats. */}
          {data && !empty && (
            <p className="text-xs t-dim leading-relaxed">{t("velocity.caveat")}</p>
          )}
        </div>
      )}
    </section>
  );
}
