import { useEffect, useRef } from "react";

/**
 * Polling hook for long-running asynchronous batch/scan operations (like email import
 * scans or property availability verification).
 *
 * Automatically polls `fetcher` on the given interval while `active` is true.
 *
 * `fetcher`/`onProgress` are read through refs on purpose: callers pass inline
 * closures that get a new identity on every render, and depending on them
 * would tear the effect down and re-run `tick()` on each render — during a
 * check that meant hammering the progress endpoint continuously instead of
 * every `intervalMs` as intended.
 */
export function useProgressPoll<T>(
  active: boolean,
  fetcher: () => Promise<T>,
  onProgress: (data: T) => void,
  intervalMs = 800,
) {
  const fetcherRef = useRef(fetcher);
  const onProgressRef = useRef(onProgress);
  fetcherRef.current = fetcher;
  onProgressRef.current = onProgress;

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetcherRef.current();
        if (!cancelled) onProgressRef.current(res);
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
  }, [active, intervalMs]);
}
