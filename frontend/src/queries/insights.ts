/** The three panels that read aggregates rather than rows.
 *
 *  Each of them used to carry the same twenty lines: a `loading` flag, an
 *  `error` string, and a monotonic request id because the city filter changes on
 *  every keystroke and a slow answer for "M" must not repaint the panel that
 *  "Milano" already filled. All three are the query key now — an answer belongs
 *  to the city it was asked about, so the wrong one has nowhere to land.
 *
 *  They used to be fetched only while their panel was open, because all three
 *  sat collapsed above the grid and an aggregate over the whole table is not
 *  something to run at somebody who came to look at listings. They have a screen
 *  of their own now, and arriving on it *is* the request: gating them behind a
 *  disclosure that no longer exists would only mean a screen that loads nothing
 *  until it is poked. The one exception is the comparables below, which are a
 *  full property fetch behind a control the user presses.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { keys } from "./keys";

export function useMarketVelocity(contract: "sale" | "rent", city: string) {
  return useQuery({
    queryKey: keys.marketVelocity(contract, city),
    queryFn: () => api.getMarketVelocity(contract, city),
  });
}

export function useScraperHealth() {
  return useQuery({
    queryKey: keys.scraperHealth,
    queryFn: () => api.getScraperHealth(),
  });
}

/** The areas with enough daily snapshots to plot a line at all. */
export function useTrendAreas(contract: "sale" | "rent") {
  return useQuery({
    queryKey: keys.trendAreas(contract),
    queryFn: () => api.getTrendAreas(contract),
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
