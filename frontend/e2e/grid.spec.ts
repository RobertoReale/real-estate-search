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

test("a row of cards reads down its columns, not across four layouts", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // The card is built on a fixed skeleton so that the same field is in the same
  // place on every card in a row — which is what lets a reader compare four
  // prices by moving their eye down instead of hunting for each one. It was not:
  // a badge row that was empty on one card and two lines on the next, a tag
  // strip that only existed once something had been tagged, and a commute row
  // that depended on a routing batch each pushed everything below them down.
  //
  // Four cards, because `xl:grid-cols-4` is what 1440px gets, and the top of
  // each zone is the assertion: heights inside a zone may differ, positions may
  // not.
  const row = cards(page);
  expect(await row.count()).toBeGreaterThanOrEqual(4);

  for (const zone of ["title", "address", "price", "facts", "market", "tags"] as const) {
    const tops: number[] = [];
    for (let i = 0; i < 4; i++) {
      const box = await row.nth(i).locator(`[data-zone="${zone}"]`).boundingBox();
      expect(box, `card ${i} has no ${zone} zone`).not.toBeNull();
      tops.push(Math.round(box!.y));
    }
    // Sub-pixel rounding is the only slack allowed: anything larger is a card
    // whose content changed where its rows are.
    const drift = Math.max(...tops) - Math.min(...tops);
    expect(drift, `the ${zone} zone sits at ${tops.join(", ")} across the row`)
      .toBeLessThanOrEqual(1);
  }
});
