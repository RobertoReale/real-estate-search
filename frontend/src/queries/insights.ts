/** The three panels that read aggregates rather than rows.
 *
 *  Each of them used to carry the same twenty lines: a `loading` flag, an
 *  `error` string, and a monotonic request id because the city filter changes on
 *  every keystroke and a slow answer for "M" must not repaint the panel that
 *  "Milano" already filled. All three are the query key now — an answer belongs
 *  to the city it was asked about, so the wrong one has nowhere to land.
 *
 *  They are still fetched only while their panel is open. These are aggregate
 *  queries over the whole table, and a collapsed accordion is not a reason to
 *  run one.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { keys } from "./keys";

export function useMarketVelocity(contract: "sale" | "rent", city: string, open: boolean) {
  return useQuery({
    queryKey: keys.marketVelocity(contract, city),
    queryFn: () => api.getMarketVelocity(contract, city),
    enabled: open,
  });
}

export function useScraperHealth(open: boolean) {
  return useQuery({
    queryKey: keys.scraperHealth,
    queryFn: () => api.getScraperHealth(),
    enabled: open,
  });
}

/** The areas with enough daily snapshots to plot a line at all. */
export function useTrendAreas(contract: "sale" | "rent", open: boolean) {
  return useQuery({
    queryKey: keys.trendAreas(contract),
    queryFn: () => api.getTrendAreas(contract),
    enabled: open,
  });
}

export function useTrend(
  contract: "sale" | "rent",
  area: { city: string; zone: string } | undefined,
) {
  return useQuery({
    queryKey: keys.trend(contract, area?.city ?? "", area?.zone ?? ""),
    queryFn: () => api.getPricingTrends(contract, area!.city, area!.zone),
    enabled: area !== undefined,
  });
}

/** The listings behind an area's current median, revealed on demand: most users
 *  want the line, and this is a full property fetch. Necessarily today's set —
 *  a snapshot keeps each past point's count, never its members. */
export function useTrendComparables(
  contract: "sale" | "rent",
  area: { city: string; zone: string } | undefined,
  open: boolean,
) {
  return useQuery({
    queryKey: keys.trendComparables(contract, area?.city ?? "", area?.zone ?? ""),
    queryFn: () => api.getPricingTrendComparables(contract, area!.city, area!.zone),
    enabled: open && area !== undefined,
  });
}
