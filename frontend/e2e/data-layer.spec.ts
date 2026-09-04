/** The three things the hand-rolled fetches protected, asserted on the product.
 *
 *  `refreshSeq`, `pruneSelection` and the `data_version` comparison were not
 *  decoration: each of them is a bug that reached a user once, and each was
 *  deleted or rewritten when the dashboard moved onto a data layer. The
 *  mechanisms are gone; the behaviours are not allowed to go with them, and a
 *  comment saying so is not a guard. These are.
 *
 *  All three are asserted from outside the app — a count on the screen, a label
 *  on a checkbox, the requests that left the browser — so they keep meaning what
 *  they mean when the components underneath are rebuilt in phases C and D.
 */
import { expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";
import { press, setTicked } from "./harness/drive";

import type { Page } from "@playwright/test";

const isGrid = (url: string) => new URL(url).pathname === "/api/properties";

/**
 * Puts the backend's "did anything change?" fingerprint under the test's
 * control, and pins the poll to its scanning cadence so a change shows up in
 * seconds rather than in the idle half-minute.
 *
 * The status itself is the real one — only the two fields this is about are
 * rewritten on the way through. Returns the setter for the fingerprint.
 */
async function fingerprint(page: Page, initial: string): Promise<(v: string) => void> {
  let version = initial;
  await page.route(
    (url) => url.pathname === "/api/scrapers/status",
    async (route) => {
      try {
        const response = await route.fetch();
        const body = await response.json();
        await route.fulfill({ json: { ...body, running: true, data_version: version } });
      } catch {
        // the page went away while this was in the air
      }
    },
  );
  return (v: string) => { version = v; };
}

/** Every grid request the browser makes, from now on. */
function gridRequests(page: Page): string[] {
  const seen: string[] = [];
  page.on("request", (request) => {
    if (isGrid(request.url())) seen.push(request.url());
  });
  return seen;
}

test("a slow answer for an abandoned filter never reaches the grid", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  // One city matches nothing and is made to answer late; the other matches the
  // whole corpus and answers at once. Typed in that order, the stale answer
  // lands last — which is exactly the sequence that used to repaint the grid
  // with results for a filter the user had already moved off.
  await page.route(
    (url) => url.pathname === "/api/properties" && url.searchParams.get("city") === "Bologna",
    async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 4000));
      try {
        await route.continue();
      } catch {
        // the page went away while this was in the air
      }
    },
  );

  await page.getByLabel("City").fill("Bologna");
  await page.waitForRequest((request) =>
    isGrid(request.url()) && new URL(request.url()).searchParams.get("city") === "Bologna");
  await page.getByLabel("City").fill("Milano");
  await expect.poll(() => resultCount(page)).toBe(all);

  // The abandoned answer arrives about here. It is a page of nothing, for a
  // filter nothing is watching, and the screen must not move.
  await page.waitForTimeout(5000);
  expect(
    await resultCount(page),
    "a superseded answer overwrote the grid — the newer filter's results were "
    + "replaced by the older filter's",
  ).toBe(all);
  await expect(cards(page).first()).toBeVisible();
});

test("select all keeps meaning the whole filtered set across a refresh", async ({ page }) => {
  const setVersion = await fingerprint(page, "before");
  const grid = gridRequests(page);

  await page.goto("/");
  await waitForResults(page);
  const total = await resultCount(page);

  await press(page, "selection.toggleMode");
  await setTicked(page, "selection.selectAll", true);
  await expect(page.getByText(`Select all (${total} of ${total})`)).toBeVisible();

  // It asked the backend for the whole set rather than counting the cards on
  // screen: `limit=0` is what the label's promise costs, and reusing the loaded
  // window instead is how "hide all 300" became "hide the first 60".
  expect(
    grid.filter((url) => new URL(url).searchParams.get("limit") === "0"),
    "select all never asked for the whole filtered set",
  ).not.toEqual([]);

  // Now a scan lands and the grid re-reads itself underneath the selection.
  const before = grid.length;
  setVersion("after");
  await expect.poll(() => grid.length, { timeout: 20_000 }).toBeGreaterThan(before);

  await expect(
    page.getByText(`Select all (${total} of ${total})`),
    "a background refresh shrank the selection to what the grid had loaded",
  ).toBeVisible();

  await press(page, "selection.toggleMode");
});

test("the grid re-reads itself when the fingerprint moves, and not before", async ({ page }) => {
  const setVersion = await fingerprint(page, "before");
  const grid = gridRequests(page);

  await page.goto("/");
  await waitForResults(page);
  // let the first load and the first poll settle, so what follows is the
  // steady state rather than the arrival
  await page.waitForTimeout(6000);
  const settled = grid.length;

  // Several polls at the scanning cadence with the fingerprint unchanged. The
  // status is asked for; the grid is not. Before the fingerprint existed this
  // window re-downloaded the whole filtered set — market position, deal score
  // and provenance computed per row — every four seconds.
  await page.waitForTimeout(9000);
  expect(
    grid.length,
    "the grid was refetched by a poll that had reported nothing had changed",
  ).toBe(settled);

  setVersion("after");
  await expect
    .poll(() => grid.length, { timeout: 20_000 })
    .toBeGreaterThan(settled);
});
