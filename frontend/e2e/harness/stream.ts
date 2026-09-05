/** A `GET /api/events` the test writes, so the backend's own state need not move.
 *
 *  Everything the stream carries — the scan running, the property fingerprint,
 *  a portal that stopped answering — is produced by work this suite is not
 *  allowed to do: a scan reaches the portals. Driving the real stream would
 *  mean either reaching the network or waiting for a batch nobody started.
 *
 *  So the connection is served from here instead. One frame per connection,
 *  then the response ends and the client reconnects on its own — which is what
 *  makes `push()` land: the app re-reads the whole world on every open, so the
 *  next open delivers whatever the test has set. That is not a workaround, it
 *  is the property the reconnection is built on, and the tests that use this
 *  lean on it deliberately.
 */
import type { Page } from "@playwright/test";
import type { ScanStatus } from "../../src/types";

/** One Server-Sent Events frame, spelled exactly as `services/events.py` writes
 *  it — a named event and its JSON body, closed by a blank line. */
export function frame(topic: string, payload: unknown): string {
  return `event: ${topic}\ndata: ${JSON.stringify(payload)}\n\n`;
}

export interface FakeStream {
  /** Change what the *next* connection will be told, in the shape the real
   *  route answers. Takes effect within one reconnection, ~250 ms. */
  push(patch: Partial<ScanStatus>): void;
  /** Refuse the stream the way a stopped backend does: the connection is not
   *  opened at all, which is the case the fallback exists for. */
  setDown(down: boolean): void;
  /** Connections actually served, so "did it come back?" has a number. */
  readonly opens: number;
}

/**
 * Serve `/api/events` from the test, seeded with what the real backend would
 * have said right now.
 *
 * Seeded rather than invented: the payload is the response model the dashboard
 * reads, and a hand-written stand-in would drift away from it the first time a
 * field is added — silently, because a missing field renders as nothing.
 *
 * Call before `page.goto`.
 */
export async function fakeEventStream(page: Page): Promise<FakeStream> {
  const seed = await page.request.get("/api/scrapers/status");
  let status = (await seed.json()) as ScanStatus;
  let down = false;
  let opens = 0;

  await page.route(
    (url) => url.pathname === "/api/events",
    async (route) => {
      if (down) {
        await route.fulfill({ status: 502, body: "" }).catch(() => {});
        return;
      }
      opens += 1;
      await route
        .fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: frame("status", status),
        })
        // the page went away while this was in the air
        .catch(() => {});
    },
  );

  return {
    push: (patch) => { status = { ...status, ...patch }; },
    setDown: (value) => { down = value; },
    get opens() { return opens; },
  };
}
