import { useState } from "react";
import { formatDate, translateCurrent, useT } from "../i18n";
import { useDebounced } from "../hooks/useDebounced";
import { useMarketVelocity } from "../queries/insights";

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
  // Debounced so typing a city costs one request when the typing pauses rather
  // than one per letter; which answer reaches the panel is settled by the key,
  // so the request id this used to keep is gone with the mechanism.
  const settledCity = useDebounced(city, 250);
  const { data, isError, error, isPending } = useMarketVelocity(contract, settledCity, open);
  const message = isError
    ? (error instanceof Error ? error.message : translateCurrent("velocity.loadFailed"))
    : "";

  const empty = data && data.areas.length === 0 && data.agencies.length === 0;

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <button data-action="velocity.toggle"
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
          {isPending && !data && <p className="text-sm t-muted">{t("common.loading")}</p>}
          {message && <p className="accent-bad text-sm">⚠️ {message}</p>}

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
