import { useEffect } from "react";

/**
 * Polling hook for long-running asynchronous batch/scan operations (like email import
 * scans or property availability verification).
 *
 * Automatically polls `fetcher` on the given interval while `active` is true.
 */
export function useProgressPoll<T>(
  active: boolean,
  fetcher: () => Promise<T>,
  onProgress: (data: T) => void,
  intervalMs = 800,
) {
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetcher();
        if (!cancelled) onProgress(res);
      } catch {
        // dropped poll requests are normal during heavy long-running server operations: keep polling
      }
    };
    tick();
    const timer = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [active, fetcher, onProgress, intervalMs]);
}
