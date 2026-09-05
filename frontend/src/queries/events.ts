/** The one connection that replaced the dashboard's timers.
 *
 *  Four things changed under this screen without anybody clicking, and each of
 *  them used to have its own `refetchInterval`: the property set every 4 s
 *  during a scan and 30 s otherwise, the availability batch and the geocoding
 *  batch every 800 ms each. A dashboard left open on a phone spent the day
 *  asking to be told nothing had happened, twice over if a second tab was open.
 *
 *  Now the backend says so once, down `GET /api/events`, and this module turns
 *  each frame into the cache write or the invalidation it means. The queries
 *  themselves are unchanged: a component still reads `useScanStatus()`, and it
 *  is the same key with the same shape in it — what moved is who decides when
 *  it is stale.
 *
 *  **`fetch`, not `EventSource`.** `EventSource` cannot send a header, and this
 *  route is behind the same optional `api_auth_token` gate as every other
 *  `/api` route (invariant 14). A stream that quietly stopped working the
 *  moment somebody set a token would be worse than no stream, and a second
 *  unauthenticated route to carry it would be worse still.
 *
 *  **The polling stays, as a fallback.** An old backend behind a new build, or
 *  anything between the browser and the process that will not carry a streaming
 *  response, has to leave a working dashboard rather than a frozen one. Three
 *  failed attempts to open the stream turn the intervals back on;
 *  `usePollingFallback()` is what the queries read to decide.
 */
import { useEffect, useSyncExternalStore } from "react";
import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { authToken } from "../services/api";
import type { AvailabilityCheckProgress, GeocodeProgress, ScanStatus } from "../types";
import { keys } from "./keys";

/** First retry, doubling from here. Short enough that a backend restart is not
 *  something the user sits through. */
const RETRY_BASE_MS = 500;
/** …and capped well inside the ten seconds a reconnection is allowed to take. */
const RETRY_CAP_MS = 5000;
/** Failed *opens* before the timers come back. A stream that opened and then
 *  ended is not one of these — that is an ordinary reconnection, and treating
 *  it as a failure would put the polling back on every restart. */
const FAILURES_BEFORE_POLLING = 3;

/* ─────────────────────── is the stream carrying us? ─────────────────────── */

let pollingFallback = false;
const listeners = new Set<() => void>();

function setPollingFallback(on: boolean): void {
  if (on === pollingFallback) return;
  pollingFallback = on;
  for (const listener of listeners) listener();
}

function subscribeToFallback(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * Should this query poll?
 *
 * `false` — the normal answer — means the stream is doing the job and an
 * interval would be pure duplication. It flips to `true` only when the stream
 * could not be opened at all, which is the one case where a timer is still the
 * difference between a live dashboard and a dead one.
 */
export function usePollingFallback(): boolean {
  return useSyncExternalStore(
    subscribeToFallback,
    () => pollingFallback,
    // Nothing has tried to connect yet wherever there is no browser to try
    // (a unit test rendering a component): poll, because that is the behaviour
    // that works without a stream.
    () => true,
  );
}

/* ────────────────────────────── the frames ────────────────────────────── */

export interface StreamEvent {
  topic: string;
  data: unknown;
}

/**
 * The complete frames in what has arrived so far, and the tail that is still
 * only half a frame.
 *
 * Split out and pure because this is the part that is easy to get subtly wrong
 * and impossible to see going wrong: a chunk boundary falls wherever TCP puts
 * it, so a frame arrives in two pieces often enough to matter and never in the
 * one run somebody watches by hand. Lines starting `:` are the server's
 * heartbeat — they carry nothing and exist so a dead socket is noticed.
 */
export function parseFrames(buffer: string): { events: StreamEvent[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: StreamEvent[] = [];
  for (const block of parts) {
    let topic = "";
    const payload: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) topic = line.slice(6).trim();
      else if (line.startsWith("data:")) payload.push(line.slice(5).trim());
    }
    if (!topic || payload.length === 0) continue;
    try {
      events.push({ topic, data: JSON.parse(payload.join("\n")) });
    } catch {
      // A frame this client cannot read is a frame it skips. The next one on
      // that topic is a whole snapshot too, so nothing stays wrong for long.
    }
  }
  return { events, rest };
}

/** What one frame means to the cache.
 *
 *  The three progress topics are written straight in rather than triggering a
 *  refetch: the frame *is* the answer that request would have come back with,
 *  serialised by the same response model, so asking again would be asking for
 *  what is already in hand. The health topic is the exception — it carries a
 *  fingerprint rather than the panel, because the panel is a thirty-day
 *  aggregate nobody should pay for every tick. */
export function applyEvent(client: QueryClient, { topic, data }: StreamEvent): void {
  switch (topic) {
    case "status":
      client.setQueryData<ScanStatus>(keys.scanStatus, data as ScanStatus);
      break;
    case "availability":
      client.setQueryData<AvailabilityCheckProgress>(
        keys.availabilityProgress,
        data as AvailabilityCheckProgress,
      );
      break;
    case "geocode":
      client.setQueryData<GeocodeProgress>(keys.geocodeProgress, data as GeocodeProgress);
      break;
    case "health":
      // A blocked scan writes no property, so the fingerprint the grid watches
      // does not move and this is the only thing that says the portal stopped
      // answering. The profile rows carry the same state as the panel.
      void client.invalidateQueries({ queryKey: keys.scraperHealth });
      void client.invalidateQueries({ queryKey: keys.profiles });
      break;
  }
}

/* ──────────────────────────── the connection ──────────────────────────── */

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Hold one stream open until it ends, applying what comes down it.
 *
 * Returns whether it ever *opened*. That distinction is the whole of the
 * fallback rule: a stream that opened and later ended is a reconnection, and a
 * stream that never opened three times running is a backend that cannot serve
 * one.
 */
async function readStream(client: QueryClient, signal: AbortSignal): Promise<boolean> {
  const token = authToken.get();
  const response = await fetch("/api/events", {
    signal,
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  // A 401 is left to the ordinary request path: the fallback poll below will
  // make one, and the auth gate it raises is the same prompt as always. There
  // is no second login here to keep in step with the first.
  if (!response.ok || !response.body) return false;
  setPollingFallback(false);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      const { events, rest } = parseFrames(buffer);
      buffer = rest;
      for (const event of events) applyEvent(client, event);
    }
  } finally {
    void reader.cancel().catch(() => {});
  }
  return true;
}

/**
 * Subscribe for as long as the dashboard is mounted.
 *
 * Mounted once, on the layout route, so it survives the URL moving between the
 * grid, a property and Settings — a stream reopened on every navigation would
 * be four timers replaced by a reconnection storm.
 */
export function useEventStream(): void {
  const client = useQueryClient();

  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    let failures = 0;

    void (async () => {
      while (!stopped) {
        try {
          const opened = await readStream(client, controller.signal);
          failures = opened ? 0 : failures + 1;
        } catch {
          // Aborted on unmount, or the socket dropped. Both end the same way:
          // count it, back off, try again.
          failures += 1;
        }
        if (stopped) return;
        if (failures >= FAILURES_BEFORE_POLLING) setPollingFallback(true);
        await sleep(Math.min(RETRY_BASE_MS * 2 ** (failures - 1), RETRY_CAP_MS));
      }
    })();

    return () => {
      stopped = true;
      controller.abort();
    };
  }, [client]);
}
