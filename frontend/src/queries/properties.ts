/** The grid, the map's full set, and every write that changes what they hold.
 *
 *  The two reads are deliberately separate queries rather than one call with a
 *  variable limit. The grid asks for a window and extends it as the user
 *  scrolls; the map and "select all" mean the whole filtered set and say so with
 *  `limit: 0`. Sharing one key would let a map's answer stand in for the grid's,
 *  which is how a paginated list quietly starts downloading everything again.
 *
 *  Every write here ends the same way: invalidate and let the backend answer.
 *  Editing the list in place was how the grid used to keep up, and it is what
 *  made a favourite toggled under the favourites filter, a hidden card and a bulk action
 *  three different code paths for the same fact — the row changed, so re-read it.
 */
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../services/api";
import type {
  AvailabilityCheckSummary, ListingAudit, Property, PropertyFilters, PropertyPage,
} from "../types";
import { usePollingFallback } from "./events";
import { keys } from "./keys";

/** One screenful. The grid used to download the whole filtered set — market
 *  position, deal score and provenance computed for every row — and re-poll it;
 *  it asks for this many and extends instead. */
export const GRID_PAGE = 60;

/** Everything the dashboard reads about properties, re-read.
 *
 *  Also the searches and the tags: a scan creates rows, a bulk action can empty
 *  a tag, and the three have always been refreshed together. */
export function useRefreshDashboard(): () => void {
  const client = useQueryClient();
  return useCallback(() => {
    void client.invalidateQueries({ queryKey: keys.properties });
    void client.invalidateQueries({ queryKey: keys.profiles });
    void client.invalidateQueries({ queryKey: keys.tags });
  }, [client]);
}

/** The grid: one page, then the next, under a key that is the filter set itself.
 *
 *  That key is the whole of the race guard the dashboard used to hand-roll. A
 *  response is stored against the filters it was asked for, so an answer for
 *  "Mil" arriving after the answer for "Milano" is written to the key nothing is
 *  watching any more — it cannot reach the screen, and there is no sequence
 *  number to get wrong. */
export function usePropertyPages(filters: PropertyFilters, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: keys.propertyPages(filters),
    queryFn: ({ pageParam }) =>
      api.getProperties(filters, { limit: GRID_PAGE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (last: PropertyPage, pages: PropertyPage[]) => {
      const loaded = pages.reduce((n, page) => n + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
    // The answer already on screen stays there while the next filter is
    // fetched, so typing dims the grid rather than blanking it. It also means
    // the count above the grid never flashes zero between two real numbers.
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** The whole filtered set. The map needs every pin — a map missing everything
 *  past the first page is not a map — and "select all" needs the same set for
 *  the same reason its label does. */
export function usePropertySet(filters: PropertyFilters, enabled: boolean) {
  return useQuery({
    queryKey: keys.propertySet(filters),
    queryFn: () => api.getProperties(filters, { limit: 0 }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** One property, read on its own — the query behind a link to it.
 *
 *  Enabled only when the grid cannot answer. A property opened from a card is
 *  already on screen, so the click costs no request; a property opened from a
 *  pasted URL, or one that has left the filtered set while its detail was open,
 *  is not in the grid at all and this is what puts it there. */
export function useProperty(id: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.property(id),
    queryFn: () => api.getProperty(id),
    enabled,
  });
}

/** Reads the whole filtered set once, on demand — what "select all" presses.
 *
 *  Through the cache rather than around it: the map may already hold this exact
 *  answer, and if it does the click costs nothing. */
export function useFetchPropertySet(): (filters: PropertyFilters) => Promise<PropertyPage> {
  const client = useQueryClient();
  return useCallback(
    (filters) => client.fetchQuery({
      queryKey: keys.propertySet(filters),
      queryFn: () => api.getProperties(filters, { limit: 0 }),
    }),
    [client],
  );
}

/* ────────────────────────── writing to one property ────────────────────────── */

/** Hide a property: it leaves the active views and scans never bring it back. */
export function useHideProperty() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (id: number) => api.deleteProperty(id),
    onSuccess: refresh,
  });
}

export function useRestoreProperty() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (id: number) => api.restoreProperty(id),
    onSuccess: refresh,
  });
}

export function useMarkPropertySold() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (id: number) => api.markPropertySold(id),
    onSuccess: refresh,
  });
}

export function useToggleFavorite() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (p: Property) =>
      api.updateProperty(p.id, { is_favorite: !p.is_favorite }),
    onSuccess: refresh,
  });
}

export function useSaveNotes() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) =>
      api.updateProperty(id, { notes }),
    onSuccess: refresh,
  });
}

/** Tag a property, creating the tag if this is the first use of the name.
 *
 *  Two calls, one mutation: `createTag` is idempotent on a case-insensitive
 *  match, so the pair is the single act the user performed and either both land
 *  or the whole thing reports failed. */
export function useAddTag() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: async ({ property, name }: { property: Property; name: string }) => {
      const tag = await api.createTag(name);
      const tagIds = [...new Set([...property.tags.map((t) => t.id), tag.id])];
      return api.updateProperty(property.id, { tag_ids: tagIds });
    },
    onSuccess: refresh,
  });
}

export function useRemoveTag() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: ({ property, tagId }: { property: Property; tagId: number }) =>
      api.updateProperty(property.id, {
        tag_ids: property.tags.map((t) => t.id).filter((id) => id !== tagId),
      }),
    onSuccess: refresh,
  });
}

/** Resolve one property's coordinates on demand. Fail-open by design: an
 *  address too vague to place answers `located: false`, which is not an error. */
export function useGeocodeProperty() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (id: number) => api.geocodeProperty(id),
    onSuccess: refresh,
  });
}

/** Probe the portal for one property, and get its updated row back. */
export function useCheckSingleProperty() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: (id: number) => api.checkSingleProperty(id),
    onSuccess: refresh,
  });
}

/* ────────────────────────── writing to many at once ────────────────────────── */

/** What the dashboard asks of the bulk endpoint. `restore` is on no button: it
 *  is what Undo sends to take back a hide or a "no longer on the market". */
export type BulkAction = "hide" | "restore" | "favorite" | "unfavorite" | "sold";

export function useBulkProperties() {
  const refresh = useRefreshDashboard();
  return useMutation({
    mutationFn: ({ ids, action }: { ids: number[]; action: BulkAction }) =>
      api.bulkProperties(ids, action),
    onSuccess: refresh,
  });
}

/** The availability batch. It runs on the backend for as long as it needs, so
 *  what is pending here is the whole sweep rather than one request. */
export function useCheckProperties() {
  const refresh = useRefreshDashboard();
  return useMutation<AvailabilityCheckSummary, Error, number[]>({
    mutationFn: (ids) => api.checkProperties(ids),
    onSuccess: refresh,
  });
}

export function useCancelPropertiesCheck() {
  return useMutation({ mutationFn: () => api.cancelPropertiesCheck() });
}

/** How far the batch has got. Pushed down the event stream, and kept out of the
 *  cache afterwards so the next batch cannot open on the last one's numbers.
 *
 *  The query stays declared so the pushed value has an observer to keep it
 *  alive — `gcTime: 0` collects a key nothing is watching — and its interval is
 *  what runs if the stream could not be opened. */
export function useAvailabilityProgress(running: boolean) {
  const polling = usePollingFallback();
  const { data } = useQuery({
    queryKey: keys.availabilityProgress,
    queryFn: () => api.propertiesCheckProgress(),
    enabled: running && polling,
    refetchInterval: polling ? 800 : false,
    gcTime: 0,
  });
  // `active: false` is the backend saying there is nothing to report — showing
  // its zeroes would replace a real count with a fresh-looking one.
  return data?.active ? data : null;
}

/* ────────────────────────── the listing reader ────────────────────────── */

/** The stored reading of this listing, or null if none was ever asked for.
 *
 *  Reads the cache only — never the model — so opening a card is free. A card
 *  nobody has ever read answers `null` rather than failing, which is why the
 *  detail shows nothing here instead of an error. */
export function useListingAudit(id: number, enabled: boolean) {
  return useQuery<ListingAudit | null>({
    queryKey: keys.listingAudit(id),
    queryFn: () => api.getPropertyAudit(id),
    enabled,
  });
}

/** Read the listing with the configured model, and put the answer where the
 *  query above will find it. */
export function useAuditProperty() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: number; force: boolean }) =>
      api.auditProperty(id, force),
    onSuccess: (audit, { id }) => client.setQueryData(keys.listingAudit(id), audit),
  });
}
