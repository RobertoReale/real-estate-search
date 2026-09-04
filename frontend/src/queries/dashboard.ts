/** The reference data every screen leans on, and the one thing that tells the
 *  dashboard when to re-read it.
 *
 *  Searches, tags and the scan status change rarely and for reasons that have
 *  nothing to do with the filters, which is why they were already fetched apart
 *  from the grid. What is new here is that they are fetched *once* for the whole
 *  application: three components asking for the searches is one request, and a
 *  mutation anywhere says they changed by naming their key.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../services/api";
import type { ScanStatus } from "../types";
import { keys } from "./keys";

export function useProfiles() {
  return useQuery({ queryKey: keys.profiles, queryFn: () => api.getProfiles() });
}

export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: () => api.getTags() });
}

/** The scan status, polled — and the poll is the cheap half of the sync model.
 *
 *  This endpoint touches two small aggregates and carries a `data_version`
 *  fingerprint of the property set, so asking "did anything change?" every few
 *  seconds costs almost nothing. What it must never become is "give me
 *  everything again": before the fingerprint existed the dashboard re-downloaded
 *  the whole filtered set every four seconds for as long as a scan ran. */
export function useScanStatus() {
  return useQuery({
    queryKey: keys.scanStatus,
    queryFn: () => api.getScanStatus(),
    refetchInterval: (query) => (query.state.data?.running ? 4000 : 30000),
  });
}

/**
 * Re-reads the dashboard when the backend says its property set moved.
 *
 * The fingerprint is the trigger and the *only* trigger: the poll above answers
 * whether anything changed, and this turns a yes into one round of invalidation.
 * The first reading of a session is adopted rather than acted on — with nothing
 * to compare it against it is not a change, and treating it as one meant every
 * load fetched the grid twice.
 */
export function useDataVersionSync(status: ScanStatus | undefined): void {
  const client = useQueryClient();
  const seen = useRef<string | null>(null);

  useEffect(() => {
    const version = status?.data_version;
    if (!version || version === seen.current) return;
    const known = seen.current !== null;
    seen.current = version;
    if (!known) return;
    void client.invalidateQueries({ queryKey: keys.properties });
    void client.invalidateQueries({ queryKey: keys.profiles });
    void client.invalidateQueries({ queryKey: keys.tags });
  }, [status?.data_version, client]);
}

/** Start a scan now. The status is marked running straight away so the button
 *  reads as pressed, and the poll above switches to its scanning cadence
 *  without waiting for its next tick. */
export function useTriggerScan() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.triggerScan(),
    onSuccess: () => {
      client.setQueryData<ScanStatus>(keys.scanStatus, (s) =>
        s ? { ...s, running: true } : s);
      void client.invalidateQueries({ queryKey: keys.scanStatus });
    },
  });
}
