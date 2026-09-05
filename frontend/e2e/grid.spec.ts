/** The dashboard with data in it: what a returning user lands on. */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";

test("the corpus is on screen on first load", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // Every demo title is "<typology> <condition> in <street>", so a card bearing
  // one is proof the grid is showing the corpus and not a placeholder.
  await expect(cards(page).first()).toContainText(/ in (Via|Viale|Largo|Vicolo) /);
  expect(await resultCount(page)).toBeGreaterThan(0);

  // The count is the whole filtered set; the grid holds one page of it.
  const count = await resultCount(page);
  expect(await cards(page).count()).toBeLessThanOrEqual(count);

  await checkScreen(page, "the grid");
});

test("the grid is the first thing a user with data can read", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // Above the fold, at the width this app is used on. It was not: the first
  // card started 1385px down, below monitored searches, scraper health, market
  // velocity and price trends, and a product whose own listings sit under three
  // panels of configuration is a product that opens on its plumbing. The panels
  // are their own screens now, and this is the assertion that keeps them there.
  const box = await cards(page).first().boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y).toBeLessThan(900);
});
