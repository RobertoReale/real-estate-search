/** One screenshot per screen, at three widths, on the same Linux the CI runner
 *  builds on.
 *
 *  Every screen already has a journey that proves it works; none of them would
 *  catch a token that shifted a card's padding everywhere at once, or a layout
 *  that only regressed at 768px. That is what this file is for, and it is the
 *  only thing it is for — no new behaviour is asserted here that the journeys
 *  above do not already cover, only the pixels those journeys never look at.
 *
 *  Two screens answer a live backend with something the seeded database has
 *  never produced, so they are pinned rather than left to whatever the run
 *  happened to catch mid-flight: a log tail is real file content that differs
 *  machine to machine, and a scan in progress is exactly the state a snapshot
 *  cannot hold still for. Everything else is read straight off the demo
 *  corpus, the same way the journeys already do.
 */
import type { Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import { cards, waitForResults } from "./harness/dashboard";
import { press } from "./harness/drive";
import { useEmptyBackend } from "./harness/empty";
import { snapshotScreen } from "./harness/visual";

async function fakeLogTail(page: Page): Promise<void> {
  await page.route("**/api/logs/tail*", (route) =>
    route.fulfill({
      json: {
        lines: [
          "2026-01-01 09:00:00 INFO scan started for Trilocale Navigli",
          "2026-01-01 09:00:04 INFO immobiliare: page 2, 41 listings",
          "2026-01-01 09:00:07 INFO scan finished, 41 listings",
        ],
        path: "/var/log/real-estate-search/app.log",
      },
    }));
}

test("the listings grid", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await snapshotScreen(page, "listings");
});

test("a property detail", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await cards(page).first().click();
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  await snapshotScreen(page, "property-detail");
});

test("insights", async ({ page }) => {
  await page.goto("/insights");
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(3);
  await snapshotScreen(page, "insights");
});

test("searches", async ({ page }) => {
  await page.goto("/searches");
  await expect(page.locator("[data-action='profiles.row.select']").first()).toBeVisible();
  await snapshotScreen(page, "searches");
});

test("the settings dialog", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await press(page, "nav.settings");
  await expect(page.getByRole("button", { name: "Salva le impostazioni" })).toBeVisible();
  await snapshotScreen(page, "settings");
});

test("the backend log", async ({ page }) => {
  await fakeLogTail(page);
  await page.goto("/logs");
  await expect(page.getByRole("heading", { name: "Log del backend" })).toBeVisible();
  await snapshotScreen(page, "logs");
});

test("activity, with nothing running", async ({ page }) => {
  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Nessuna scansione in corso" })).toBeVisible();
  await snapshotScreen(page, "activity");
});

test("the capability setup", async ({ page }) => {
  await page.goto("/setup");
  await expect(page.getByRole("heading", { name: "Configura quello che ti serve" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Salva e continua" })).toBeVisible();
  await snapshotScreen(page, "setup");
});

test("the guided first run", async ({ page }) => {
  await useEmptyBackend(page);
  await page.goto("/");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/start");
  await expect(page.getByRole("heading", { name: "Ricerca Immobili" })).toBeVisible();
  await snapshotScreen(page, "onboarding");
});
