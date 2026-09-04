/** Every query key the dashboard uses, in one place.
 *
 *  A key is the identity of a piece of server state: two components asking with
 *  the same key are one read, and a mutation says what it changed by naming a
 *  prefix. They are written here rather than at the call sites because a key
 *  spelled two ways is two caches that never hear about each other — nothing
 *  breaks loudly, a panel simply stops refreshing and the reason is invisible.
 *
 *  The nesting is the invalidation plan. `properties` is the prefix everything
 *  about the grid hangs off, so one `invalidateQueries({ queryKey: keys.properties })`
 *  after a write covers the window, the whole set and every filter combination
 *  still in the cache. The reads that must *not* be swept by that — a listing's
 *  stored audit, the availability batch's progress — deliberately sit outside it.
 */
import type { PropertyFilters } from "../types";

export const keys = {
  /** Everything the grid shows, under one prefix so a write invalidates it all. */
  properties: ["properties"] as const,
  /** One window at a time, extended as the user scrolls. */
  propertyPages: (filters: PropertyFilters) => ["properties", "pages", filters] as const,
  /** The whole filtered set (`limit: 0`): what the map needs — a pin per
   *  property — and what "select all" has to mean. */
  propertySet: (filters: PropertyFilters) => ["properties", "set", filters] as const,
  /** One property, by id: what an address opens when the grid has no such row.
   *  Under the same prefix as the grid on purpose — a favourite or a note
   *  written from the detail view invalidates both in one call. */
  property: (id: number) => ["properties", "one", id] as const,

  /** Outside the `properties` prefix on purpose: a reading already paid for must
   *  not be re-requested every time a card is favourited. */
  listingAudit: (id: number) => ["listing-audit", id] as const,
  /** Likewise: the batch's own progress, polled while it runs. */
  availabilityProgress: ["availability-progress"] as const,

  profiles: ["search-profiles"] as const,
  profileResults: (ids: readonly number[]) => ["search-profiles", "results", ids] as const,
  tags: ["tags"] as const,
  scanStatus: ["scan-status"] as const,
  settings: ["settings"] as const,

  marketVelocity: (contract: string, city: string) =>
    ["market-velocity", contract, city] as const,
  scraperHealth: ["scraper-health"] as const,
  trendAreas: (contract: string) => ["pricing-trends", "areas", contract] as const,
  trend: (contract: string, city: string, zone: string) =>
    ["pricing-trends", "points", contract, city, zone] as const,
  trendComparables: (contract: string, city: string, zone: string) =>
    ["pricing-trends", "comparables", contract, city, zone] as const,

  backups: ["backups"] as const,
  geocodeProgress: ["geocode-progress"] as const,
  logTail: (lines: number) => ["logs", lines] as const,
};
