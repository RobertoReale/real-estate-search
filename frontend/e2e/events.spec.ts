/** The four promises the event stream replaced the timers on.
 *
 *  The timers were not wrong — they worked, which is why they survived so long.
 *  What they cost was invisible from inside the app: a dashboard left open all
 *  day asked to be told nothing had happened roughly twenty thousand times, and
 *  the only place that shows up is the network log. So this spec asserts on the
 *  network log, and on the two things the change is only acceptable *with* — a
 *  connection that comes back on its own, and timers that come back if it
 *  cannot.
 *
 *  Three of the four drive the stream from the test rather than from the
 *  backend (`harness/stream.ts` says why). The first one deliberately does not:
 *  "nothing is being asked for" is a claim about the real connection, and a
 *  fake one that ends after a frame would prove the opposite of what is wanted.
 */
import { expect, test } from "./fixtures";
import { waitForResults } from "./harness/dashboard";
import { press } from "./harness/drive";
import { fakeEventStream } from "./harness/stream";

import type { Page } from "@playwright/test";

/** Every API request the browser makes from now on, except the stream itself. */
function apiRequests(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    const { pathname } = new URL(request.url());
    if (pathname.startsWith("/api/") && pathname !== "/api/events") seen.push(pathname);
  });
  return seen;
}

test("an idle dashboard asks for nothing for a solid minute", async ({ page }) => {
  const asked = apiRequests(page);

  await page.goto("/");
  await waitForResults(page);
  // The load itself is requests, and so is the stream's first frame arriving.
  // What is being measured starts after all of that has settled.
  await page.waitForTimeout(5000);
  asked.length = 0;

  await page.waitForTimeout(60_000);

  expect(
    asked,
    "the dashboard was still polling with the stream connected — these paths "
    + "were asked for during a minute in which nobody touched anything",
  ).toEqual([]);
});

test("a scan runs from start to summary without the screen asking anything", async ({ page }) => {
  const stream = await fakeEventStream(page);
  // A scan reaches the portals, which the suite may not. The button is still
  // pressed for real; only what it asks for is answered from here.
  await page.route("**/api/scrapers/trigger", (route) =>
    route.fulfill({ json: { status: "started" } }));
  const asked = apiRequests(page);
  const statusReads = () => asked.filter((path) => path === "/api/scrapers/status").length;

  await page.goto("/");
  await waitForResults(page);
  await page.waitForTimeout(2000);
  const settled = statusReads();

  // The press marks the status running on the spot and then checks that guess,
  // which is one request and the last one in this test. It is not a poll — it
  // happens because somebody clicked, and it happens once.
  await press(page, "scan.now");
  await expect.poll(statusReads).toBe(settled + 1);
  const afterPress = statusReads();

  // From here the scan is the backend's business, and everything the screen
  // learns about it, it is told. First that it is running…
  stream.push({ running: true });
  await expect(page.getByText("Scan in progress")).toBeVisible({ timeout: 10_000 });

  // …then that it is over, with something to report.
  stream.push({ running: false, last_summary: "14 new listings" });
  await expect(page.getByText("14 new listings")).toBeVisible({ timeout: 10_000 });

  expect(
    statusReads(),
    "the scan status was polled — after the press, the stream is supposed to be "
    + "what says the scan is running and what says it finished",
  ).toBe(afterPress);
});

test("a backend that goes away and comes back is reconnected to within ten seconds", async ({ page }) => {
  const stream = await fakeEventStream(page);

  await page.goto("/");
  await waitForResults(page);
  await expect.poll(() => stream.opens).toBeGreaterThan(0);

  // The process goes down. Six seconds is long enough for the backoff to reach
  // its ceiling, so what is measured below is the worst case rather than the
  // lucky one that retries a moment after the socket is refused.
  stream.setDown(true);
  await page.waitForTimeout(6000);

  const before = stream.opens;
  stream.push({ last_summary: "back from the dead" });
  stream.setDown(false);
  const restarted = Date.now();

  await expect
    .poll(() => stream.opens, { timeout: 10_000 })
    .toBeGreaterThan(before);
  expect(Date.now() - restarted).toBeLessThan(10_000);

  // Reconnected is not the claim; carrying again is. The stream opens by
  // resending the whole world, so the state set while it was down is on screen
  // without anybody reloading the page.
  await expect(page.getByText("back from the dead")).toBeVisible({ timeout: 10_000 });
});

test("a stream that cannot be opened at all puts the timers back", async ({ page }) => {
  // Not "down and coming back" this time: down for good, which is what an old
  // backend behind a new build looks like, or a proxy that will not carry a
  // streaming response. The dashboard has to stay live anyway.
  await page.route((url) => url.pathname === "/api/events", (route) =>
    route.fulfill({ status: 503, body: "" }).catch(() => {}));
  const asked = apiRequests(page);

  await page.goto("/");
  await waitForResults(page);
  await page.waitForTimeout(5000);
  const settled = asked.filter((path) => path === "/api/scrapers/status").length;

  // Three refused opens turn the intervals back on, and the idle cadence is
  // thirty seconds — so this is the poll that used to be unconditional,
  // happening because and only because the stream could not be had.
  await expect
    .poll(
      () => asked.filter((path) => path === "/api/scrapers/status").length,
      { timeout: 60_000 },
    )
    .toBeGreaterThan(settled);
});
