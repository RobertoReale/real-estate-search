import { useMemo, useState } from "react";
import { formatDate, formatNumber, translateCurrent, useT } from "../i18n";
import { useTrend, useTrendAreas, useTrendComparables } from "../queries/insights";
import { formatPrice } from "../services/api";
import type { PricingTrend, Property } from "../types";
import { ICON_SIZE, PriceDrop, PriceRise, Trend, Warning } from "../ui/icons";

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
    : translateCurrent("trends.wholeCity", { city: a.city || "—" });

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
      aria-label={translateCurrent("trends.chartAria")}>
      <polyline points={line} fill="none"
        className="stroke-accent-graph" strokeWidth={2}
        strokeLinejoin="round" strokeLinecap="round" />
      {geom.pts.map((p) => (
        <circle key={p.date} cx={p.x} cy={p.y} r={2.5}
          className="fill-accent-graph-point">
          <title>
            {translateCurrent("trends.pointTooltip", {
              date: formatDate(p.date),
              value: formatNumber(Math.round(p.v)),
            })}
          </title>
        </circle>
      ))}
    </svg>
  );
}

export default function PriceTrends({ contract, city, onOpenProperty }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  // What the user picked, if they picked anything. The area actually plotted is
  // derived below, so an areas list that arrives (or changes with the contract)
  // never leaves the chart pointing at something that is no longer offered.
  const [picked, setPicked] = useState("");
  // The area the comparables were revealed for. Holding the key rather than a
  // boolean is what closes the list when the chart moves to another area: the
  // listings behind one median say nothing about another's.
  const [revealedFor, setRevealedFor] = useState<string | null>(null);

  const areasQuery = useTrendAreas(contract, open);
  const areas = useMemo(() => areasQuery.data ?? [], [areasQuery.data]);

  // Prefer the whole-city aggregate of the city currently filtered, else fall
  // back to the first (most-observed) area.
  const selected = useMemo(() => {
    if (areas.some((a) => areaKey(a) === picked)) return picked;
    const wanted = city.trim().toLowerCase();
    const match = areas.find((a) => a.zone === "" && a.city === wanted) ?? areas[0];
    return match ? areaKey(match) : "";
  }, [areas, picked, city]);
  const area = areas.find((a) => areaKey(a) === selected);

  const trendQuery = useTrend(contract, area);
  const trend = trendQuery.data;
  const compsOpen = revealedFor !== null && revealedFor === selected;
  const compsQuery = useTrendComparables(contract, area, compsOpen);
  const comps = compsOpen ? compsQuery.data : undefined;

  // One line for whichever of the three refused, in the order the panel reads
  // them, and each with its own fallback: "the areas could not be listed" and
  // "the chart could not be drawn" are different failures to the reader.
  const [failed, fallback] = areasQuery.error
    ? [areasQuery.error, "trends.areasFailed" as const]
    : trendQuery.error
      ? [trendQuery.error, "trends.trendFailed" as const]
      : [compsQuery.error, "trends.listingsFailed" as const];
  const error = !failed
    ? ""
    : failed instanceof Error && failed.message
      ? failed.message
      : translateCurrent(fallback);

  const stats = useMemo(() => {
    if (!trend || trend.points.length < 2) return null;
    const first = trend.points[0].median_sqm_price;
    const last = trend.points[trend.points.length - 1].median_sqm_price;
    return { first, last, changePct: ((last - first) / first) * 100 };
  }, [trend]);

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <button data-action="trends.toggle"
        className="w-full flex flex-wrap items-center justify-between gap-2 text-left"
        onClick={() => setOpen(!open)}>
        <h2 className="flex items-center gap-1.5 font-semibold text-base">
          <Trend className="shrink-0" />
          {t("trends.title")}{" "}
          <span className="t-muted text-sm font-normal">{t("trends.subtitle")}</span>
        </h2>
        <span className="t-muted text-sm">{open ? t("health.hide") : t("health.show")}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          {areasQuery.isPending && !areas.length && (
            <p className="text-sm t-muted">{t("common.loading")}</p>
          )}
          {error && <p className="accent-bad text-sm inline-flex items-center gap-1.5"><Warning /> {error}</p>}

          {!areasQuery.isPending && !error && areas.length === 0 && (
            <div className="panel rounded-xl p-6 text-center text-sm t-muted">
              <p className="flex justify-center mb-2 t-dim"><Trend size={ICON_SIZE.display} strokeWidth={1.25} /></p>
              {t("trends.empty")}
            </div>
          )}

          {areas.length > 0 && (
            <>
              <select data-action="trends.area" className="input w-full sm:w-72"
                value={selected} onChange={(e) => setPicked(e.target.value)}>
                {areas.map((a) => (
                  <option key={areaKey(a)} value={areaKey(a)}>
                    {t("trends.areaOption", { label: areaLabel(a), days: a.point_count })}
                  </option>
                ))}
              </select>

              {trend && trend.points.length >= 2 && (
                <div>
                  <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-2 text-sm">
                    <span className="t-strong text-lg font-semibold tnum">
                      {t("common.sqmPrice", {
                        value: formatNumber(
                          Math.round(trend.points[trend.points.length - 1].median_sqm_price),
                        ),
                      })}
                    </span>
                    {stats && (
                      <span className={`inline-flex items-center gap-1
                        ${stats.changePct >= 0 ? "accent-bad" : "accent-good"}`}>
                        {stats.changePct >= 0 ? <PriceRise /> : <PriceDrop />}
                        {t("trends.changeSince", {
                          pct: Math.abs(stats.changePct).toFixed(1),
                          date: formatDate(trend.points[0].captured_on),
                        })}
                      </span>
                    )}
                  </div>
                  <TrendChart points={trend.points} />
                  <p className="text-xs t-dim mt-2">{t("trends.caveat")}</p>
                </div>
              )}

              {trend && trend.points.length < 2 && (
                <p className="text-sm t-muted">{t("trends.oneDayOnly")}</p>
              )}

              {/* The concrete listings behind the median. Loaded on demand:
                  most users just want the trend line, and this is a full
                  property fetch. Necessarily the CURRENT set — snapshots keep
                  only each past point's count, never its members. */}
              {trend && (
                <div className="pt-1">
                  <button data-action="trends.comparables"
                    className="text-sm accent-link hover:underline"
                    onClick={() => setRevealedFor(compsOpen ? null : selected)}>
                    {t(compsOpen ? "trends.hideComparables" : "trends.showComparables")}
                  </button>

                  {compsOpen && (
                    <div className="mt-2">
                      {compsQuery.isPending && <p className="text-sm t-muted">{t("common.loading")}</p>}
                      {comps && comps.length === 0 && (
                        <p className="text-sm t-muted">{t("trends.comparablesEmpty")}</p>
                      )}
                      {comps && comps.length > 0 && (() => {
                        const med = trend.points[trend.points.length - 1]?.median_sqm_price;
                        return (
                          <>
                            <p className="text-xs t-dim mb-2">
                              {t(
                                comps.length === 1
                                  ? "trends.comparablesNoteOne"
                                  : "trends.comparablesNote",
                                { count: comps.length },
                              )}
                            </p>
                            <ul className="space-y-1 tnum">
                              {comps.map((p) => {
                                const sqm = p.current_min_price && p.sqm
                                  ? p.current_min_price / p.sqm : null;
                                const delta = sqm && med ? (sqm - med) / med * 100 : null;
                                return (
                                  <li key={p.id}>
                                    <button data-action="trends.openProperty"
                                      onClick={() => onOpenProperty(p)}
                                      className="w-full text-left flex flex-wrap items-baseline gap-x-2 gap-y-0.5 p-2 rounded-lg panel hover:border-accent-line transition">
                                      <span className="text-sm font-medium truncate max-w-full">
                                        {p.title || t("card.untitled")}
                                      </span>
                                      {p.zone && (
                                        <span className="text-xs t-dim">· {p.zone}</span>
                                      )}
                                      <span className="text-sm ml-auto">
                                        {formatPrice(p.current_min_price, p.contract)}
                                      </span>
                                      {sqm && (
                                        <span className="text-xs t-muted w-full sm:w-auto">
                                          {t("common.sqmPrice", {
                                            value: formatNumber(Math.round(sqm)),
                                          })}
                                          {delta !== null && (
                                            <span className={delta <= 0 ? "accent-good" : "accent-bad"}>
                                              {t("trends.vsMedian", {
                                                sign: delta > 0 ? "+" : "",
                                                pct: delta.toFixed(0),
                                              })}
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
