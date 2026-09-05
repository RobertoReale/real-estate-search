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
import { usePollingFallback } from "./events";
import { keys } from "./keys";

export function useProfiles() {
  return useQuery({ queryKey: keys.profiles, queryFn: () => api.getProfiles() });
}

export function useTags() {
  return useQuery({ queryKey: keys.tags, queryFn: () => api.getTags() });
}

/** The scan status, pushed — and the `data_version` fingerprint that rides
 *  along with it is what tells the grid to re-read itself.
 *
 *  The stream (`queries/events.ts`) writes this key directly, with the payload
 *  this same route would have answered. The interval below is the fallback and
 *  nothing else: it is off whenever the stream is carrying, which is the
 *  ordinary case, and it is the old cadence — 4 s while a scan runs, 30 s
 *  otherwise — whenever it is not.
 *
 *  What this must never become is "give me everything again": before the
 *  fingerprint existed the dashboard re-downloaded the whole filtered set every
 *  four seconds for as long as a scan ran. */
export function useScanStatus() {
  const polling = usePollingFallback();
  return useQuery({
    queryKey: keys.scanStatus,
    queryFn: () => api.getScanStatus(),
    refetchInterval: (query) =>
      polling ? (query.state.data?.running ? 4000 : 30000) : false,
  });
}

/**
 * Re-reads the dashboard when the backend says its property set moved.
 *
 * The fingerprint is the trigger and the *only* trigger: the stream says what
 * the fingerprint is now, and this turns a change into one round of
 * invalidation. Deliberately reading the *key* rather than the stream, so it
 * behaves identically whichever put the value there — the fallback poll writes
 * the same field.
 *
 * The first reading of a session is adopted rather than acted on — with nothing
 * to compare it against it is not a change, and treating it as one meant every
 * load fetched the grid twice. Everything after it is compared by value, which
 * is what makes a reconnection free: the stream opens by resending the whole
 * world, and a fingerprint that has not moved is not a change.
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
 *  reads as pressed rather than waiting on the stream's next frame — a control
 *  that does not visibly respond to being pressed reads as a broken one, and
 *  the first thing a scan does is spend a second resolving a search.
 *
 *  It is a guess, so it is checked — and the stream cannot be what checks it.
 *  The stream publishes *changes*; a flag this client wrote to its own cache is
 *  not a change the backend knows about, so a scan that never actually started
 *  (already running, nothing to scan) would leave the button reading "Running…"
 *  with nothing on its way to say otherwise. One request after a deliberate
 *  press is the correction, and it is not a poll: it happens because somebody
 *  clicked. */
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
