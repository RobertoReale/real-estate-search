/** The median €/sqm of one area, over the days it was observed.
 *
 *  Still dependency-free inline SVG — a charting library is 90kB to draw one
 *  line — but no longer the bare polyline it was. Four things separate a chart
 *  from a squiggle, and each is here for a reason a reader can check:
 *
 *  - **an area fill**, so the eye reads the height of the line rather than
 *    hunting for its slope;
 *  - **a faint grid**, which is what makes two points at similar heights
 *    comparable at a glance;
 *  - **an emphasised endpoint**, because on a price chart the question is
 *    almost always "and where is it now";
 *  - **an empty state**, because a chart of nothing used to render as an empty
 *    box, and an empty box is indistinguishable from a broken one.
 *
 *  The axis labels are HTML in a gutter beside the SVG, not `<text>` inside it.
 *  The drawing scales to its container, and anything inside the viewBox scales
 *  with it: type that is 7px on a phone and 16px on a monitor is type that was
 *  never sized.
 */
import { useId, useMemo } from "react";

import { CHART, chartGeometry } from "./chart";
import { formatDate, formatNumber, useT } from "../../i18n";
import type { PricingTrend } from "../../types";
import { cx, EmptyState } from "../../ui";
import { ICON_SIZE, Trend } from "../../ui/icons";

/** Beyond this many days the dots stop being points and become a thick band, so
 *  only the line, the fill and the endpoint are drawn. */
const DOTS_FIT = 40;

export default function TrendChart({ points }: { points: PricingTrend["points"] }) {
  const t = useT();
  const fill = useId();
  const geom = useMemo(() => chartGeometry(points), [points]);

  if (!geom) {
    return (
      <EmptyState className="panel rounded-xl"
        icon={<Trend size={ICON_SIZE.display} strokeWidth={1.25} />}
        title={t("trends.chartEmpty")}
        description={t("trends.chartEmptyHint")} />
    );
  }

  const { w, h, padX } = CHART;
  const last = geom.points[geom.points.length - 1];
  // One point is a reading, not a trend: it gets the grid and the endpoint, and
  // the line and its fill wait for the second day.
  const drawLine = geom.points.length > 1;
  const label = (value: number, y: number) => (
    <span className="absolute left-0 w-10 pr-2 text-right text-2xs t-dim tnum -translate-y-1/2"
      style={{ top: `${(y / h) * 100}%` }}>
      {formatNumber(Math.round(value))}
    </span>
  );

  return (
    <figure className="m-0 max-w-3xl">
      <div className="relative pl-10">
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto text-accent-graph"
          role="img" aria-label={t("trends.chartAria")}>
          <defs>
            {/* `currentColor` at both stops: the gradient inherits the accent
                from the <svg>, so one class recolours the line and its fill
                together, and the dark theme's token applies to both. */}
            <linearGradient id={fill} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity={0.28} />
              <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
            </linearGradient>
          </defs>

          {/* `non-scaling-stroke` throughout: a hairline is a hairline at 390px
              and at 1440px, and without it the grid thickens into the chart. */}
          <g className="stroke-line" strokeWidth={1} vectorEffect="non-scaling-stroke"
            opacity={0.6}>
            {geom.grid.map((y) => (
              <line key={y} x1={padX} x2={w - padX} y1={y} y2={y} />
            ))}
          </g>

          {drawLine && (
            <>
              <path d={geom.area} fill={`url(#${fill})`} />
              <polyline points={geom.line} fill="none" stroke="currentColor"
                strokeWidth={2} vectorEffect="non-scaling-stroke"
                strokeLinejoin="round" strokeLinecap="round" />
            </>
          )}

          {geom.points.length <= DOTS_FIT && geom.points.map((p) => (
            <circle key={p.date} cx={p.x} cy={p.y} r={2.5}
              className="fill-accent-graph-point">
              <title>
                {t("trends.pointTooltip", {
                  date: formatDate(p.date), value: formatNumber(Math.round(p.value)),
                })}
              </title>
            </circle>
          ))}

          {/* Where it is now: a halo, then the dot over it, ringed in the panel
              colour so it stays visible where the line doubles back over it. */}
          <circle cx={last.x} cy={last.y} r={8} fill="currentColor" opacity={0.18} />
          <circle cx={last.x} cy={last.y} r={4} className="fill-accent-graph-point stroke-surface"
            strokeWidth={2}>
            <title>
              {t("trends.pointTooltip", {
                date: formatDate(last.date), value: formatNumber(Math.round(last.value)),
              })}
            </title>
          </circle>
        </svg>

        {label(geom.max, geom.yOfMax)}
        {geom.min !== geom.max && label(geom.min, geom.yOfMin)}
      </div>

      {/* The x axis, such as it is: where the history starts and where it ends.
          A single reading is centred under the dot it belongs to. */}
      <figcaption className={cx("pl-10 mt-1 flex gap-2 text-2xs t-dim tnum",
        drawLine ? "justify-between" : "justify-center")}>
        <span>{formatDate(geom.points[0].date)}</span>
        {drawLine && <span>{formatDate(last.date)}</span>}
      </figcaption>

      {!drawLine && <p className="mt-2 text-sm t-muted">{t("trends.oneDayOnly")}</p>}
    </figure>
  );
}
