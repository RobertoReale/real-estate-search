/** Where a listing sits against its market — as *one* statement.
 *
 *  The backend hands the card two overlapping verdicts. `sqm_price_delta_pct`
 *  is the plain comparison against the median €/sqm of the zone (or of the
 *  city, when the zone has too few comparables). `deal_score` starts from that
 *  same delta — `deal_score.py` sets `base = -sqm_price_delta_pct` — and then
 *  shifts it for condition and agency cues. Rendered side by side they read as
 *  two independent findings that happen to agree, and when a cue has moved the
 *  score they read as two findings that disagree: "18% below market" next to
 *  "16% below neighborhood average" is a card arguing with itself.
 *
 *  So one wins, by precedence, and the loser is not shown at all:
 *
 *  1. the Deal Score, when it is decisive (undervalued/overpriced) **and** it
 *     says something the raw delta does not. "Fair" adds nothing to a card that
 *     is already showing a price, and a score that has not moved off its base
 *     is the delta wearing different words.
 *  2. otherwise the median comparison, beyond ±5%. Smaller deltas are market
 *     noise: a listing 2% off the median is at the median.
 *  3. otherwise nothing, and the card's status row stays empty. It is a fixed
 *     row either way, so an empty one costs no layout.
 *
 *  **Invariant 22.** Only the five listing-derived fields below are read. The
 *  OMI band (`omi_min_sqm_price` / `omi_max_sqm_price`) is a different measure
 *  from a different source and is never substituted for the listing median, nor
 *  folded into this decision; the detail view presents it separately and
 *  labelled. Nothing here recomputes `deal_score` or `deal_label` — the
 *  precedence chooses which backend verdict to *show*, and shows it as given.
 */
import type { Property } from "../types";

export type MarketPosition =
  /** The Deal Score's verdict. `pct` is `|deal_score|`, exactly as computed. */
  | { kind: "deal"; under: boolean; pct: number; reasons: string[] }
  /** The listing median comparison, with the median itself for the tooltip. */
  | {
      kind: "median";
      below: boolean;
      pct: number;
      scope: "zone" | "city";
      median: number | null;
    };

/** Deltas smaller than this are noise rather than a market position. */
const NOISE_PCT = 5;

export function marketPosition(p: Property): MarketPosition | null {
  const delta = p.sqm_price_delta_pct;
  const decisive =
    p.deal_score !== null && (p.deal_label === "undervalued" || p.deal_label === "overpriced");
  const restatesDelta = delta !== null && p.deal_score !== null
    && Math.round(-delta) === p.deal_score;

  if (decisive && !restatesDelta) {
    return {
      kind: "deal",
      under: p.deal_label === "undervalued",
      pct: Math.abs(p.deal_score as number),
      reasons: p.deal_reasons ?? [],
    };
  }
  if (delta !== null && Math.abs(delta) >= NOISE_PCT) {
    return {
      kind: "median",
      below: delta < 0,
      pct: Math.round(Math.abs(delta)),
      scope: p.area_median_scope === "zone" ? "zone" : "city",
      median: p.area_median_sqm_price,
    };
  }
  return null;
}
