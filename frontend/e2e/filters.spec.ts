/** Narrowing the grid, and getting back out of it.
 *
 *  Counts are read from the result header and compared against each other rather
 *  than against literals: the corpus is deterministic, but which of its eighty
 *  properties are still active depends on what the journeys before this one did,
 *  and a suite that has to be renumbered whenever a test is added is a suite
 *  people stop adding tests to.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";
import { fill, press } from "./harness/drive";

test("filtering by city, by price and by contract, then resetting", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  // City — the corpus is one city, so the name matches everything and a
  // different one matches nothing. Both directions matter: a filter that
  // silently ignores its input looks identical to one that has nothing to hide.
  //
  // `exact` because setting the field also raises the chip that takes it back
  // off again, and that chip is labelled "Remove the City: Milano filter" —
  // `getByLabel` matches on substring, so the field has to ask for its own name.
  await page.getByLabel("City", { exact: true }).fill("Milano");
  await expect.poll(() => resultCount(page)).toBe(all);

  await page.getByLabel("City", { exact: true }).fill("Bologna");
  await expect.poll(() => resultCount(page)).toBe(0);
  await expect(page.getByText("Nothing collected matches these filters.")).toBeVisible();
  await checkScreen(page, "the grid with nothing matching");

  await page.getByLabel("City", { exact: true }).fill("");
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
  await page.getByRole("group", { name: "Market" }).getByRole("button", { name: "Rent" })
    .click();
  await waitForResults(page);
  await expect(page.getByText(/^Min price €\s*\/mo$/)).toBeVisible();
  await expect(cards(page).first()).toContainText("rent");

  // Reset — every filter goes, the Buy/Rent world the user is in stays.
  await page.getByRole("button", { name: "↺ Reset filters" }).click();
  await expect(page.getByLabel(/^Max price €/)).toHaveValue("");
  await page.getByRole("group", { name: "Market" }).getByRole("button", { name: "Buy" })
    .click();
  await expect.poll(() => resultCount(page)).toBe(all);
});

test("a filter that matches nothing says so about this machine, and offers the portals",
  async ({ page }) => {
    await page.goto("/listings");
    await waitForResults(page);

    // The size of the pile being sifted, read off the rail rather than written
    // here: it is the number the empty state has to name, and a literal would
    // break the moment a journey before this one hides a property.
    const collected = (await page.getByText(/^\d+ listings collected$/).innerText())
      .replace(/\D/g, "");
    expect(Number(collected)).toBeGreaterThan(0);

    await fill(page, "filters.query", "villa con eliporto");
    await page.getByLabel("City", { exact: true }).fill("Bologna");
    await expect.poll(() => resultCount(page)).toBe(0);

    // The sentence that is the whole point: not "there are no such houses" —
    // a claim about the market, made by something that only looked here — but
    // none among the ones already collected.
    await expect(page.getByText(`None of the ${collected} listings collected so far fit.`,
      { exact: false })).toBeVisible();

    await press(page, "app.toPortals");
    await expect(page).toHaveURL(/\/searches\?/);
    await expect(page.getByRole("heading",
      { name: "Started from the filters you had on Listings" })).toBeVisible();

    // What maps, maps; what does not is named rather than quietly discarded.
    // A search that looks for half of what was typed is the failure this whole
    // handover exists to avoid.
    await expect(page.getByText("City: Bologna")).toBeVisible();
    await expect(page.getByText("Not carried over")).toBeVisible();
    await expect(page.getByText(/Keyword: villa con eliporto —/)).toBeVisible();
    await checkScreen(page, "the searches screen reached from a filter");
  });
