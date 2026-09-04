/** Everything the monitored-searches panel writes, plus the two things it asks
 *  the backend to work out for it.
 *
 *  The panel is one state machine with five modes; what it needed from a data
 *  layer is small and specific. A save can touch two portals and therefore two
 *  rows, so it is one mutation that loops rather than two the caller sequences —
 *  a half-saved pair is not a state the list should ever be left in. And every
 *  one of them ends by invalidating the searches: the panel used to tell its
 *  parent to refetch through a callback, which worked only because the parent
 *  happened to be the component that owned the fetch.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../services/api";
import type { SearchBuilderParams, SearchProfile } from "../types";
import { keys } from "./keys";

/** The searches changed, and so may the properties they are credited with. */
export function useRefreshProfiles(): () => void {
  const client = useQueryClient();
  return useCallback(() => {
    void client.invalidateQueries({ queryKey: keys.profiles });
    void client.invalidateQueries({ queryKey: keys.properties });
  }, [client]);
}

export function useBulkProfiles() {
  const refresh = useRefreshProfiles();
  return useMutation({
    mutationFn: ({ ids, action, notifyChannels, deleteResults }: {
      ids: number[];
      action: "activate" | "pause" | "notify" | "delete";
      notifyChannels?: string;
      deleteResults?: boolean;
    }) => api.bulkProfiles(ids, action, { notifyChannels, deleteResults }),
    onSuccess: refresh,
  });
}

/**
 * Renames a set of searches, one PUT each.
 *
 * The route takes a whole search rather than a patch, so every field goes back
 * unchanged with the new name. Sent as a bare `{ name }` this answered 422 and
 * Merge and Separate silently did nothing; resending the URL untouched also
 * keeps the backend from reading this as a new search and re-arming the
 * baseline (invariant 3).
 */
export function useRenameProfiles() {
  const refresh = useRefreshProfiles();
  return useMutation({
    mutationFn: async (renames: { profile: SearchProfile; name: string }[]) => {
      for (const { profile, name } of renames) {
        await api.updateProfile(profile.id, {
          name,
          search_url: profile.search_url,
          excluded_keywords: profile.excluded_keywords ?? "",
          notify_channels: profile.notify_channels ?? "",
          is_active: profile.is_active,
        });
      }
    },
    onSuccess: refresh,
  });
}

/** One search saved, created or updated. Several of them per press, in order,
 *  because a builder save can cover both portals. */
export interface ProfileWrite {
  /** The row to overwrite, or null to create a new search. */
  id: number | null;
  data: Partial<SearchProfile>;
}

export function useSaveProfiles() {
  const refresh = useRefreshProfiles();
  return useMutation({
    mutationFn: async (writes: ProfileWrite[]) => {
      for (const { id, data } of writes) {
        if (id === null) await api.createProfile(data);
        else await api.updateProfile(id, data);
      }
    },
    onSuccess: refresh,
  });
}

/** What deleting these searches would cost, asked for the selection as a whole:
 *  a property found by two of the searches being deleted is not one "another
 *  search keeps". */
export function useProfileResults(ids: number[] | null) {
  return useQuery({
    queryKey: keys.profileResults(ids ?? []),
    queryFn: () => api.getProfilesResults(ids!),
    enabled: ids !== null && ids.length > 0,
    gcTime: 0,
  });
}

/** Build the portal URLs from structured criteria. `verify` asks Idealista, with
 *  one live request, whether it knows the zone's slug — off for the calls that
 *  merely re-derive a URL to prefill a form. */
export function useBuildSearchUrls() {
  return useMutation({
    mutationFn: ({ params, verify }: { params: SearchBuilderParams; verify: boolean }) =>
      api.buildSearchUrls(params, verify),
  });
}

export function useParseSearchUrl() {
  return useMutation({ mutationFn: (url: string) => api.parseSearchUrl(url) });
}

export function useAskAssistant() {
  return useMutation({ mutationFn: (query: string) => api.askAssistant(query) });
}
