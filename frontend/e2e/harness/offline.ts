/** The rule that keeps the browser suite offline: it may talk to its own two
 *  servers and to nothing else.
 *
 *  A test that quietly depends on a tile server, a placeholder-image service or
 *  a geocoder is a flake generator — it goes red on somebody else's outage, and
 *  it is slowest on the day you most need an answer. Worse, portal traffic from
 *  a test run lands on the same residential IP the real scans depend on, which
 *  is the one resource this project cannot buy back.
 *
 *  So the suite does not merely avoid the network: an attempt to reach it is
 *  aborted and recorded, and the recording fails the test. Silence is not
 *  evidence — a request that was never made and a request that was made and
 *  succeeded look identical from inside a passing test.
 */
import type { BrowserContext } from "@playwright/test";
import { BACKEND_ORIGIN, PREVIEW_ORIGIN } from "./ports";

/** Both spellings of the loopback address: the app is served from one and calls
 *  the other through the preview proxy, and a redirect can swap them. */
const ALLOWED = new Set(
  [BACKEND_ORIGIN, PREVIEW_ORIGIN].flatMap((origin) => [
    origin,
    origin.replace("127.0.0.1", "localhost"),
  ]),
);

export interface OfflineGuard {
  /** Every off-harness URL the page asked for, in order, blocked before it left. */
  readonly attempted: string[];
  /**
   * Declares that a screen this journey visits asks for an address the guard
   * will block, and that this is the tested behaviour rather than a defect.
   *
   * There is exactly one of these today: the map's OpenStreetMap tiles. A map
   * without a tile server is the offline case, not a special case — the pins,
   * the zone drawing and the switch back to the grid all have to work with the
   * backdrop missing, which is also what a user on a dead connection sees. The
   * request is still aborted, so the promise that nothing reaches the network
   * is unchanged; what changes is only whether the block ends the test.
   */
  expectBlocked(pattern: RegExp): void;
  /** What was blocked and *not* declared — the failure, if there is one. */
  readonly unexpected: string[];
}

/** Arms the guard on a context. Returns the (live) record of what it blocked. */
export async function installOfflineGuard(context: BrowserContext): Promise<OfflineGuard> {
  const attempted: string[] = [];
  const declared: RegExp[] = [];

  await context.route("**/*", async (route) => {
    const url = route.request().url();
    let allowed: boolean;
    try {
      const parsed = new URL(url);
      // `data:` and `blob:` never leave the browser — the demo corpus carries
      // its photos as data URIs precisely so they cannot. Only http(s) is a
      // request somebody could be listening for.
      allowed = !/^https?:$/.test(parsed.protocol) || ALLOWED.has(parsed.origin);
    } catch {
      allowed = false;
    }

    if (allowed) {
      await route.continue();
      return;
    }
    attempted.push(url);
    await route.abort("blockedbyclient");
  });

  return {
    attempted,
    expectBlocked: (pattern: RegExp) => declared.push(pattern),
    get unexpected() {
      return attempted.filter((url) => !declared.some((pattern) => pattern.test(url)));
    },
  };
}

/** The message a blocked request produces, phrased as the fix rather than the symptom. */
export function offlineViolation(attempted: readonly string[]): string {
  return [
    "the page tried to reach an address outside the harness:",
    ...[...new Set(attempted)].map((url) => `  ${url}`),
    "",
    "The suite runs with no network by construction. Either the code under test",
    "gained a remote dependency it should not have, or the fixture it renders",
    "needs to carry its own data the way the demo corpus carries its photos.",
  ].join("\n");
}
