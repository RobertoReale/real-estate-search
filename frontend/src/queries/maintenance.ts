/** The long-running housekeeping jobs, the copies of the database, and the log.
 *
 *  Three of these are batches the backend runs on its own thread: geocoding,
 *  commutes and the restart. What is "pending" for them is the whole sweep
 *  rather than one request, which is exactly what a mutation already means — so
 *  the busy flags each of them used to carry by hand are the mutation's own
 *  `isPending`, and there is no longer a `finally` that can forget to clear one.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import { keys } from "./keys";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/* ────────────────────────── coordinates ────────────────────────── */

/** Backfill the pins for properties a geographic filter would otherwise drop.
 *  The grid carries the coordinates, so it is re-read when this lands. */
export function useGeocodeMissing() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.geocodeMissing(),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.properties }),
  });
}

export function useCancelGeocode() {
  return useMutation({ mutationFn: () => api.cancelGeocode() });
}

/** Forget the cached misses, so a transient Nominatim failure stops reading as
 *  an address that can never be placed. */
export function useClearGeocodeCache() {
  return useMutation({ mutationFn: () => api.clearGeocodeCache() });
}

/** How far the sweep has got. Polled only while one is running, and dropped
 *  from the cache afterwards so the next sweep cannot open on stale numbers. */
export function useGeocodeProgress(running: boolean) {
  const { data } = useQuery({
    queryKey: keys.geocodeProgress,
    queryFn: () => api.geocodeProgress(),
    enabled: running,
    refetchInterval: 800,
    gcTime: 0,
  });
  return data?.active ? data : null;
}

/* ────────────────────────── travel times ────────────────────────── */

/** Route every property/saved-place pair that is not cached yet. The grid only
 *  ever reads cached legs, so this is what makes commute times appear at all. */
export function useComputeCommutes() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.computeCommutes(),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.properties }),
  });
}

/* ────────────────────────── the copies of the database ────────────────────────── */

export function useBackups() {
  return useQuery({ queryKey: keys.backups, queryFn: () => api.listBackups() });
}

export function useCreateBackup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.createBackup(),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.backups }),
  });
}

/** Bring in a `case.db` carried from another install. It joins the list; putting
 *  it over the live database is the separate, explicit restore below. */
export function useImportBackup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.importBackup(file),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.backups }),
  });
}

/** Replace the live database with a copy. Nothing is invalidated on success on
 *  purpose: the whole UI is now looking at different data, and the caller
 *  reloads the page rather than patching a cache row by row. */
export function useRestoreBackup() {
  return useMutation({ mutationFn: (name: string) => api.restoreBackup(name) });
}

export function useResetData() {
  return useMutation({
    mutationFn: (scope: "dashboard" | "pricing-snapshots" | "factory") =>
      api.resetData(scope),
  });
}

/* ────────────────────────── the process itself ────────────────────────── */

/** What a restart attempt ended as. Three outcomes and they need different
 *  words: the backend that cannot restart itself is a bootstrap trap rather
 *  than a failure, and it deserves to be named as one. */
export type RestartOutcome = "too-old" | "no-return";

/**
 * Restart the backend and wait for it to answer again, then reload the page so
 * the whole UI is talking to the fresh process.
 *
 * The wait is part of the action rather than something the caller does after it:
 * the request itself does not return — the socket drops as the process goes down
 * — so "did it work?" is only answerable by asking the new process. A resolved
 * mutation here means the restart did *not* complete; the success path never
 * resolves, because the page is gone.
 */
export function useRestartBackend() {
  return useMutation<RestartOutcome, Error, void>({
    mutationFn: async () => {
      try {
        await api.restartBackend();
      } catch (e) {
        const raw = e instanceof Error ? e.message : String(e);
        // A 404/405 means THIS backend predates the restart route, so it cannot
        // restart itself. Say so plainly instead of polling a process that
        // never went down and pretending it worked.
        if (/Method Not Allowed|Not Found|Error 40[45]/i.test(raw)) return "too-old";
        // Otherwise the socket dropped as the process went down, which is the
        // expected path: the poll below is the real "did it come back?" signal.
      }
      await sleep(1500); // give it a moment to actually go down first
      const deadline = Date.now() + 40000;
      while (Date.now() < deadline) {
        try {
          await api.getScanStatus();
          window.location.reload();
          await sleep(60000); // the page is going; never resolve past here
        } catch {
          await sleep(1000);
        }
      }
      return "no-return";
    },
  });
}

/* ────────────────────────── the backend's own log ────────────────────────── */

/**
 * The tail of `app.log`, refreshed while the viewer asks for it.
 *
 * The out-of-order guard the viewer used to carry is gone with the mechanism
 * that needed it: one key means one request in flight, so a tail that resolves
 * late is a tail nothing is waiting for. It used to be possible for an
 * abandoned effect's answer to land on top of a newer one, which on a backend
 * slow enough to make anyone open this viewer is the older tail winning.
 */
export function useLogTail(lines: number, autoRefresh: boolean) {
  return useQuery({
    queryKey: keys.logTail(lines),
    queryFn: () => api.logsTail(lines),
    refetchInterval: autoRefresh ? 3000 : false,
    gcTime: 0,
  });
}
