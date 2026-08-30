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
  // Known to fail, and recorded rather than fixed: at 1440×900 the first card
  // starts 1385px down, below monitored searches, scraper health, market
  // velocity, price trends and the filter bar. That is the information
  // architecture rather than a layout slip, and it is task D.1 that moves the
  // panels. Declaring it here keeps the finding in the suite instead of in a
  // note nobody reads: when D.1 lands, Playwright reports this as "expected to
  // fail but passed" and the annotation comes off in the same commit.
  test.fail();

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // Above the fold, at the width this app is used on: a product whose own
  // listings are below three panels of configuration is a product that opens on
  // its plumbing. (Phase D moves the panels; this is the assertion that says
  // whether it has to.)
  const box = await cards(page).first().boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y).toBeLessThan(900);
});
