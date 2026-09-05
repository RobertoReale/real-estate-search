/** What the price looks like against the market — every figure labelled with
 *  what it measures.
 *
 *  The card picks exactly one market statement (`utils/marketPosition.ts`)
 *  because a card has no room to explain the difference between two. Here both
 *  badges are welcome and the panel under them says whose number each is: this
 *  is the screen where the explanation fits.
 *
 *  **Invariant 22** lives in `PriceBenchmarks` below. The listing median and the
 *  OMI band are different measurements from different sources, neither ever
 *  stands in for the other, and neither is ever rendered bare.
 */
import { formatNumber, useT } from "../../i18n";
import { formatPrice } from "../../services/api";
import type { Property } from "../../types";
import { Chip } from "../../ui";
import { Deal, Price } from "../../ui/icons";
import { formatSemester } from "../../utils/format";

/** Badge comparing this property's €/sqm to the local median.
 *  Only shown beyond ±5%: smaller deltas are market noise, not signal. */
export function MarketBadge({ property: p }: { property: Property }) {
  const t = useT();
  if (p.sqm_price_delta_pct === null || Math.abs(p.sqm_price_delta_pct) < 5) {
    return null;
  }
  const below = p.sqm_price_delta_pct < 0;
  const scope = t(p.area_median_scope === "zone" ? "card.scopeZone" : "card.scopeCity");
  const pct = Math.abs(p.sqm_price_delta_pct).toFixed(0);
  return (
    <span
      title={t("card.medianIn", {
        scope,
        value: formatNumber(Math.round(p.area_median_sqm_price ?? 0)),
      })}>
      <Chip tone={below ? "positive" : "caution"} className="font-semibold">
        {t(below ? "card.belowAverage" : "card.aboveAverage", { pct, scope })}
      </Chip>
    </span>
  );
}

/** The "16% below market" badge from the Deal Score. Shown only when the
 *  verdict is decisive (undervalued/overpriced); "fair" adds no signal. A
 *  positive score means priced below the local market. */
export function DealBadge({ property: p }: { property: Property }) {
  const t = useT();
  if (p.deal_score === null || p.deal_label === "fair" || p.deal_label === null) {
    return null;
  }
  // The Deal Score's base is exactly the market-position delta (deal_score.py:
  // base = -sqm_price_delta_pct); condition/agency cues then shift it. When
  // nothing shifted it, this badge just restates the MarketBadge with the same
  // number in different words ("18% above market" next to "18% above city
  // average") — a confusing duplicate. Drop it in that case: the MarketBadge
  // already carries the €/sqm position, and DealBadge earns its place only when
  // it says something more (a renovation/agency adjustment moved the score).
  if (
    p.sqm_price_delta_pct !== null &&
    Math.round(-p.sqm_price_delta_pct) === p.deal_score
  ) {
    return null;
  }
  const under = p.deal_label === "undervalued";
  return (
    <span title={(p.deal_reasons ?? []).join(" · ") || t("card.dealScore")}>
      <Chip tone={under ? "positive" : "caution"} className="font-semibold">
        <Deal />{" "}
        {t(under ? "card.dealBelowMarket" : "card.dealAboveMarket", {
          pct: Math.abs(p.deal_score),
        })}
      </Chip>
    </span>
  );
}

/** The two price references, side by side and each labelled with what it is.
 *
 *  They are not the same measurement and must never be shown as if they were:
 *  the median is the middle of what comparable **ads ask**, the OMI band is
 *  min/max €/sqm the Agenzia delle Entrate derives from **recorded
 *  transactions**, and asking prices sit systematically above transacted ones.
 *  Averaging them, or letting one stand in for the other, would produce a
 *  number that means nothing and looks authoritative (invariant 22) — so each
 *  column says whose figure it is, the OMI one carries the semester it was
 *  recorded in, and neither is ever rendered bare.
 *
 *  A property with no OMI data shows the median alone, in a single column: an
 *  empty second box would read as a figure that failed to load. With neither,
 *  the panel is absent entirely. */
function PriceBenchmarks({ property: p }: { property: Property }) {
  const t = useT();
  const median = p.area_median_sqm_price;
  const omi = p.omi_min_sqm_price && p.omi_max_sqm_price && p.omi_semester
    ? {
        min: p.omi_min_sqm_price,
        max: p.omi_max_sqm_price,
        semester: p.omi_semester,
        stale: p.omi_stale,
      }
    : null;
  if (!median && !omi) return null;
  const scope = t(p.area_median_scope === "zone" ? "card.scopeZone" : "card.scopeCity");
  return (
    <div className="rounded-xl panel p-3 text-sm">
      <p className="font-medium mb-2">{t("benchmark.title")}</p>
      <div className={`grid gap-3 ${median && omi ? "sm:grid-cols-2" : "grid-cols-1"}`}>
        {median && (
          <div>
            <p className="text-xs t-muted">{t("benchmark.askingLabel")}</p>
            <p className="font-semibold tnum">
              {t("common.sqmPrice", { value: formatNumber(Math.round(median)) })}
            </p>
            <p className="text-2xs t-dim">{t("benchmark.askingScope", { scope })}</p>
          </div>
        )}
        {omi && (
          <div>
            <p className="text-xs t-muted">
              {t(p.contract === "rent" ? "benchmark.omiRentLabel" : "benchmark.omiSaleLabel")}
            </p>
            <p className="font-semibold tnum">
              {t(p.contract === "rent" ? "benchmark.rangeMonthly" : "benchmark.range", {
                min: formatNumber(Math.round(omi.min)),
                max: formatNumber(Math.round(omi.max)),
              })}
            </p>
            <p className="text-2xs t-dim">
              {t("benchmark.omiSource", {
                zone: p.omi_zone_code,
                semester: formatSemester(omi.semester),
              })}
            </p>
            {omi.stale && (
              <p className="mt-1">
                <span title={t("benchmark.staleNote")}>
                  <Chip tone="caution" className="font-semibold">{t("benchmark.stale")}</Chip>
                </span>
              </p>
            )}
          </div>
        )}
      </div>
      {median && omi && <p className="mt-2 text-2xs t-dim">{t("benchmark.note")}</p>}
      {/* Required by the licence on the OMI supply, so it is tied to the figures
          being on screen rather than to the panel: with the median alone there is
          nothing here of the Agenzia's to credit. */}
      {omi && <p className="mt-2 text-2xs t-dim">{t("benchmark.attribution")}</p>}
    </div>
  );
}

/** Why the Deal Score says what it says, and what it suggests offering. Shown
 *  as given: nothing here recomputes the score, the label or the range. */
function DealBreakdown({ property: p }: { property: Property }) {
  const t = useT();
  if (p.deal_score === null || p.deal_label === "fair") return null;
  return (
    <div className="rounded-xl panel p-3 text-sm">
      <p className="flex items-center gap-1.5 font-medium mb-1">
        <Deal className="shrink-0" />
        {t("detail.dealScoreTitle")}{" "}
        <span className={p.deal_score > 0 ? "accent-good" : "accent-bad"}>
          {p.deal_score > 0 ? "+" : ""}{p.deal_score}%
        </span>{" "}
        <span className="t-muted">
          ({t(p.deal_label === "undervalued"
            ? "detail.dealBelowLocal"
            : "detail.dealAboveLocal")})
        </span>
      </p>
      {p.deal_reasons && p.deal_reasons.length > 0 && (
        <ul className="list-disc list-inside t-body text-xs space-y-0.5">
          {p.deal_reasons.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}
      {p.target_price_low && p.target_price_high && (
        <p className="mt-2 t-body">
          <Price className="inline align-[-0.125em]" />{" "}
          {t("detail.suggestedProposal")}{" "}
          <span className="font-semibold tnum">
            {formatPrice(p.target_price_low, p.contract)} –{" "}
            {formatPrice(p.target_price_high, p.contract)}
          </span>
        </p>
      )}
      <p className="mt-2 text-2xs t-dim">{t("detail.dealDisclaimer")}</p>
    </div>
  );
}

/** Both references and the score's reasoning, as one block of the right-hand
 *  column. Renders nothing at all for a property with neither. */
export function Benchmarks({ property }: { property: Property }) {
  return (
    <div className="space-y-3">
      <PriceBenchmarks property={property} />
      <DealBreakdown property={property} />
    </div>
  );
}
