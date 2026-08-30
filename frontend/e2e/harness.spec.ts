/** Does the harness itself work?
 *
 *  Not a journey — those are what the rest of `e2e/` will be. This proves the
 *  three claims everything else rests on: the app is served from the production
 *  build, it is talking to the harness's own seeded backend, and the offline
 *  guard actually blocks rather than merely being installed. A guard nobody has
 *  seen fire is a guard nobody knows is wired up.
 */
import { expect, test } from "./fixtures";
import { installOfflineGuard } from "./harness/offline";
import { BACKEND_ORIGIN } from "./harness/ports";

test("the dashboard loads against the seeded harness backend", async ({ page }) => {
  const properties = page.waitForResponse(
    (response) => response.url().includes("/api/properties?") && response.ok(),
  );

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Real Estate Search" })).toBeVisible();

  // The corpus is what answered, not an empty database: every demo title is
  // "<typology> <condition> in <street>", and a card's accessible name is its
  // title (src/components/PropertyCard.tsx).
  const payload = await (await properties).json();
  expect(payload.total).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: / in (Via|Viale|Largo|Vicolo) / }).first())
    .toBeVisible();
});

test("the backend under test is the harness's own, not a developer's", async ({ request }) => {
  // Port 8137, never 8000: `scripts/windows/start.bat` owns that one, and with
  // it the real backend/case.db. The corpus lives only in the throwaway data
  // directory, so finding it here is proof of which database answered.
  const response = await request.get(`${BACKEND_ORIGIN}/api/properties?limit=1&status=all`);
  expect(response.ok()).toBe(true);
  const page = await response.json();
  expect(page.items[0].city).toBe("Milano");
});

test("the offline guard blocks anything outside the harness", async ({ browser }) => {
  // Its own context: the guard the fixture installs covers the one the tests
  // use, and this has to watch a guard fire without failing the test it fires in.
  const context = await browser.newContext();
  try {
    const guard = await installOfflineGuard(context);
    const page = await context.newPage();

    // Reserved by RFC 2606 to never resolve, so even a guard that did nothing
    // would put no traffic on the wire.
    await expect(page.goto("https://blocked.invalid/")).rejects.toThrow(/ERR_BLOCKED_BY_CLIENT/);
    expect(guard.attempted).toEqual(["https://blocked.invalid/"]);
  } finally {
    await context.close();
  }
});
