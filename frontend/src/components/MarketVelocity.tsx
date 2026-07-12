import { useCallback, useEffect, useRef, useState } from "react";
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
      setError(e instanceof Error ? e.message : "Could not load statistics");
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
          📊 Market velocity{" "}
          <span className="t-muted text-sm font-normal">
            how fast {contract === "rent" ? "rentals" : "listings"} leave the
            market, and how agencies price them
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
              {data.total_properties} properties tracked
              {city && <> in “{city}”</>}, {data.closed_properties} left the
              market
              {data.tracking_since && (
                <> · observed since{" "}
                  {new Date(data.tracking_since).toLocaleDateString()}</>
              )}
              . Areas and agencies with fewer than {data.min_sample}{" "}
              observations are not shown.
            </p>
          )}

          {empty && (
            <div className="panel rounded-xl p-6 text-center text-sm t-muted">
              <p className="text-2xl mb-2">⏳</p>
              Not enough history yet. These signals need at least{" "}
              {data?.min_sample} properties per area and a few weeks of scans
              before they mean anything — the database is still filling up.
            </div>
          )}

          {data && data.areas.length > 0 && (
            <div>
              <h3 className="font-medium text-sm mb-2">
                Neighborhoods{" "}
                <span className="t-muted font-normal">
                  (fastest-moving first)
                </span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="t-muted text-xs text-left">
                    <tr className="border-b border-slate-200 dark:border-slate-700/50">
                      <th className="py-2 pr-3 font-medium">Area</th>
                      <th className="py-2 px-3 font-medium text-right">Tracked</th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Median days between the first time a scan saw the listing and the day it disappeared">
                        Days to exit
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Median days the still-online listings have been sitting there">
                        Still listed
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Share of tracked properties that left the market">
                        Left market
                      </th>
                      <th className="py-2 pl-3 font-medium text-right"
                        title="Share of tracked properties whose price dropped at least once">
                        Cut price
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
                              whole city
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
                Agencies{" "}
                <span className="t-muted font-normal">
                  (who asks above the local median, and who discounts)
                </span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="t-muted text-xs text-left">
                    <tr className="border-b border-slate-200 dark:border-slate-700/50">
                      <th className="py-2 pr-3 font-medium">Agency</th>
                      <th className="py-2 px-3 font-medium text-right">Listings</th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Median €/sqm compared to the median of the same neighborhood. Positive = asks more than the area.">
                        vs area €/sqm
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Share of this agency's listings whose price dropped at least once">
                        Cut price
                      </th>
                      <th className="py-2 px-3 font-medium text-right"
                        title="Median discount among the listings that were actually reduced">
                        Typical cut
                      </th>
                      <th className="py-2 pl-3 font-medium text-right">Days to exit</th>
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
            <p className="text-xs t-dim leading-relaxed">
              “Left market” means no scan has seen the listing for a week: sold,
              rented, withdrawn, or republished under a new id — not proof of a
              sale. Days-on-market are counted from the day <em>this app</em>{" "}
              first saw the listing, so properties that were already online when
              you added the search look younger than they are. Both distortions
              fade as the database ages.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
