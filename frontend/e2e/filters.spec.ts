/** Narrowing the grid, and getting back out of it.
 *
 *  Counts are read from the filter bar and compared against each other rather
 *  than against literals: the corpus is deterministic, but which of its eighty
 *  properties are still active depends on what the journeys before this one did,
 *  and a suite that has to be renumbered whenever a test is added is a suite
 *  people stop adding tests to.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";

test("filtering by city, by price and by contract, then resetting", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  // City — the corpus is one city, so the name matches everything and a
  // different one matches nothing. Both directions matter: a filter that
  // silently ignores its input looks identical to one that has nothing to hide.
  await page.getByLabel("City").fill("Milano");
  await expect.poll(() => resultCount(page)).toBe(all);

  await page.getByLabel("City").fill("Bologna");
  await expect.poll(() => resultCount(page)).toBe(0);
  await expect(page.getByText("No properties match the current filters.")).toBeVisible();
  await checkScreen(page, "the grid with nothing matching");

  await page.getByLabel("City").fill("");
  await expect.poll(() => resultCount(page)).toBe(all);

  // Price — a ceiling under the cheapest sale keeps nothing, and every card
  // that survives a real ceiling asks less than it.
  await page.getByLabel(/^Max price €/).fill("300000");
  await expect.poll(() => resultCount(page)).toBeLessThan(all);
  await waitForResults(page);
  const prices = await cards(page).getByText(/^€[\d.,]+$/).allInnerTexts();
  expect(prices.length).toBeGreaterThan(0);
  for (const price of prices) {
    expect(Number(price.replace(/\D/g, ""))).toBeLessThanOrEqual(300000);
  }

  // Contract — Buy and Rent are separate worlds, and the rent side prices per
  // month. The price ceiling above stays applied, which is what makes the
  // switch visible in the count rather than merely in the label.
  await page.getByRole("group", { name: "Market" }).getByRole("button", { name: "🔑 Rent" })
    .click();
  await waitForResults(page);
  await expect(page.getByText(/^Min price €\s*\/mo$/)).toBeVisible();
  await expect(cards(page).first()).toContainText("🔑 rent");

  // Reset — every filter goes, the Buy/Rent world the user is in stays.
  await page.getByRole("button", { name: "↺ Reset filters" }).click();
  await expect(page.getByLabel(/^Max price €/)).toHaveValue("");
  await page.getByRole("group", { name: "Market" }).getByRole("button", { name: "🏠 Buy" })
    .click();
  await expect.poll(() => resultCount(page)).toBe(all);
});
