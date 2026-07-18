import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, formatPrice } from "../services/api";
import type { PricingTrend, Property, TrendArea } from "../types";

interface Props {
  contract: "sale" | "rent";
  city: string;
  /** Open a comparable in the shared detail modal (App owns the selection). */
  onOpenProperty: (p: Property) => void;
}

const areaKey = (a: { city: string; zone: string }) => `${a.city}|${a.zone}`;
const areaLabel = (a: { city: string; zone: string }) =>
  a.zone
    ? `${a.zone} · ${a.city}`
    : `${a.city || "—"} · whole city`;

/** Dependency-free SVG line chart of median €/sqm over time. The viewBox lets
 *  it scale to its container; a strict grid is overkill for a handful of daily
 *  points, so it shows the line, its endpoints, and min/max/latest labels. */
function TrendChart({ points }: { points: PricingTrend["points"] }) {
  const W = 320;
  const H = 120;
  const PAD = 8;
  const geom = useMemo(() => {
    const xs = points.map((p) => new Date(p.captured_on).getTime());
    const ys = points.map((p) => p.median_sqm_price);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    // pad the y-range by 5% so the line is not glued to the edges
    const padY = (maxY - minY) * 0.05 || maxY * 0.05 || 1;
    const loY = minY - padY;
    const spanY = maxY + padY - loY || 1;
    const px = (t: number) => PAD + ((t - minX) / spanX) * (W - 2 * PAD);
    const py = (v: number) => H - PAD - ((v - loY) / spanY) * (H - 2 * PAD);
    return {
      pts: points.map((p, i) => ({
        x: px(xs[i]), y: py(ys[i]), v: p.median_sqm_price,
        date: p.captured_on,
      })),
      minY, maxY,
    };
  }, [points]);

  const line = geom.pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
      aria-label="Median price per square meter over time">
      <polyline points={line} fill="none"
        className="stroke-blue-500 dark:stroke-blue-400" strokeWidth={2}
        strokeLinejoin="round" strokeLinecap="round" />
      {geom.pts.map((p) => (
        <circle key={p.date} cx={p.x} cy={p.y} r={2.5}
          className="fill-blue-600 dark:fill-blue-300">
          <title>{`${new Date(p.date).toLocaleDateString()}: ${Math.round(
            p.v
          ).toLocaleString("en-IE")} €/sqm`}</title>
        </circle>
      ))}
    </svg>
  );
}

export default function PriceTrends({ contract, city, onOpenProperty }: Props) {
  const [open, setOpen] = useState(false);
  const [areas, setAreas] = useState<TrendArea[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [trend, setTrend] = useState<PricingTrend | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // The listings behind the current median, revealed on demand. Reset whenever
  // the selected area changes, so the list never lags behind the chart above it.
  const [comps, setComps] = useState<Property[] | null>(null);
  const [compsOpen, setCompsOpen] = useState(false);
  const [compsLoading, setCompsLoading] = useState(false);
  const compsSeq = useRef(0);

  // monotonic ids per request (like App.tsx's refreshSeq): `city` changes on
  // every keystroke, so a slow older response must never overwrite the state
  // set by a newer one
  const areasSeq = useRef(0);
  const trendSeq = useRef(0);

  const loadAreas = useCallback(async () => {
    const seq = ++areasSeq.current;
    setLoading(true);
    try {
      const list = await api.getTrendAreas(contract);
      if (seq !== areasSeq.current) return;
      setAreas(list);
      setError("");
      // Prefer the whole-city aggregate of the city currently filtered, else
      // fall back to the first (most-observed) area.
      const wanted = city.trim().toLowerCase();
      const match = list.find((a) => a.zone === "" && a.city === wanted)
        ?? list[0];
      setSelected(match ? areaKey(match) : "");
    } catch (e) {
      if (seq !== areasSeq.current) return;
      setError(e instanceof Error ? e.message : "Could not load trends");
    } finally {
      if (seq === areasSeq.current) setLoading(false);
    }
  }, [contract, city]);

  // debounced like App.tsx's refresh: one request when typing pauses
  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(loadAreas, 250);
    return () => window.clearTimeout(t);
  }, [open, loadAreas]);

  useEffect(() => {
    if (!open || !selected) {
      setTrend(null);
      return;
    }
    const area = areas.find((a) => areaKey(a) === selected);
    if (!area) return;
    const seq = ++trendSeq.current;
    api.getPricingTrends(contract, area.city, area.zone)
      .then((t) => {
        if (seq === trendSeq.current) setTrend(t);
      })
      .catch((e) => {
        if (seq === trendSeq.current) {
          setError(e instanceof Error ? e.message : "Could not load trend");
        }
      });
  }, [open, selected, areas, contract]);

  // A new area (or contract) invalidates any revealed comparable list.
  useEffect(() => {
    setComps(null);
    setCompsOpen(false);
  }, [selected, contract]);

  async function toggleComparables() {
    if (compsOpen) {
      setCompsOpen(false);
      return;
    }
    setCompsOpen(true);
    if (comps) return; // already loaded for this area
    const area = areas.find((a) => areaKey(a) === selected);
    if (!area) return;
    const seq = ++compsSeq.current;
    setCompsLoading(true);
    try {
      const list = await api.getPricingTrendComparables(contract, area.city, area.zone);
      if (seq === compsSeq.current) setComps(list);
    } catch (e) {
      if (seq === compsSeq.current) {
        setError(e instanceof Error ? e.message : "Could not load the listings");
      }
    } finally {
      if (seq === compsSeq.current) setCompsLoading(false);
    }
  }

  const stats = useMemo(() => {
    if (!trend || trend.points.length < 2) return null;
    const first = trend.points[0].median_sqm_price;
    const last = trend.points[trend.points.length - 1].median_sqm_price;
    return { first, last, changePct: ((last - first) / first) * 100 };
  }, [trend]);

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <button
        className="w-full flex flex-wrap items-center justify-between gap-2 text-left"
        onClick={() => setOpen(!open)}>
        <h2 className="font-semibold text-base">
          📈 Price trends{" "}
          <span className="t-muted text-sm font-normal">
            how the median €/sqm has moved over time in your tracked areas
          </span>
        </h2>
        <span className="t-muted text-sm">{open ? "Hide ▲" : "Show ▼"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          {loading && !areas.length && <p className="text-sm t-muted">Loading…</p>}
          {error && <p className="accent-bad text-sm">⚠️ {error}</p>}

          {!loading && !error && areas.length === 0 && (
            <div className="panel rounded-xl p-6 text-center text-sm t-muted">
              <p className="text-2xl mb-2">⏳</p>
              No history to chart yet. The app records one median per area per
              day; a trend line needs at least two days of scans before it means
              anything — come back in a couple of days.
            </div>
          )}

          {areas.length > 0 && (
            <>
              <select className="input w-full sm:w-72"
                value={selected} onChange={(e) => setSelected(e.target.value)}>
                {areas.map((a) => (
                  <option key={areaKey(a)} value={areaKey(a)}>
                    {areaLabel(a)} ({a.point_count} days)
                  </option>
                ))}
              </select>

              {trend && trend.points.length >= 2 && (
                <div>
                  <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-2 text-sm">
                    <span className="t-strong text-lg font-semibold">
                      {Math.round(
                        trend.points[trend.points.length - 1].median_sqm_price
                      ).toLocaleString("en-IE")} €/sqm
                    </span>
                    {stats && (
                      <span className={stats.changePct >= 0 ? "accent-bad" : "accent-good"}>
                        {stats.changePct >= 0 ? "▲" : "▼"}{" "}
                        {Math.abs(stats.changePct).toFixed(1)}% since{" "}
                        {new Date(trend.points[0].captured_on).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                  <TrendChart points={trend.points} />
                  <p className="text-xs t-dim mt-2">
                    Median asking price per square meter among the listings this
                    app was tracking each day — your own sample, not the whole
                    market. It moves with what you monitor as much as with prices.
                  </p>
                </div>
              )}

              {trend && trend.points.length < 2 && (
                <p className="text-sm t-muted">
                  Only one day recorded for this area so far — the line appears
                  once there are at least two.
                </p>
              )}

              {/* The concrete listings behind the median. Loaded on demand:
                  most users just want the trend line, and this is a full
                  property fetch. Necessarily the CURRENT set — snapshots keep
                  only each past point's count, never its members. */}
              {trend && (
                <div className="pt-1">
                  <button
                    className="text-sm accent-link hover:underline"
                    onClick={toggleComparables}>
                    {compsOpen
                      ? "Hide the listings behind this median ▲"
                      : "🔍 Show the listings behind this median ▼"}
                  </button>

                  {compsOpen && (
                    <div className="mt-2">
                      {compsLoading && <p className="text-sm t-muted">Loading…</p>}
                      {comps && comps.length === 0 && (
                        <p className="text-sm t-muted">
                          No priced listings in this area right now.
                        </p>
                      )}
                      {comps && comps.length > 0 && (() => {
                        const med = trend.points[trend.points.length - 1]?.median_sqm_price;
                        return (
                          <>
                            <p className="text-xs t-dim mb-2">
                              The {comps.length} listing{comps.length > 1 ? "s" : ""}{" "}
                              currently priced in this area — the live set today's
                              median is computed from. Earlier points on the chart
                              kept only their count, so their exact listings can no
                              longer be shown. Click one to open its details.
                            </p>
                            <ul className="space-y-1">
                              {comps.map((p) => {
                                const sqm = p.current_min_price && p.sqm
                                  ? p.current_min_price / p.sqm : null;
                                const delta = sqm && med ? (sqm - med) / med * 100 : null;
                                return (
                                  <li key={p.id}>
                                    <button
                                      onClick={() => onOpenProperty(p)}
                                      className="w-full text-left flex flex-wrap items-baseline gap-x-2 gap-y-0.5 p-2 rounded-lg panel hover:border-blue-500/50 transition">
                                      <span className="text-sm font-medium truncate max-w-full">
                                        {p.title || "Untitled"}
                                      </span>
                                      {p.zone && (
                                        <span className="text-xs t-dim">· {p.zone}</span>
                                      )}
                                      <span className="text-sm ml-auto">
                                        {formatPrice(p.current_min_price, p.contract)}
                                      </span>
                                      {sqm && (
                                        <span className="text-xs t-muted w-full sm:w-auto">
                                          {Math.round(sqm).toLocaleString("en-IE")} €/sqm
                                          {delta !== null && (
                                            <span className={delta <= 0 ? "accent-good" : "accent-bad"}>
                                              {" "}({delta > 0 ? "+" : ""}{delta.toFixed(0)}% vs median)
                                            </span>
                                          )}
                                        </span>
                                      )}
                                    </button>
                                  </li>
                                );
                              })}
                            </ul>
                          </>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
