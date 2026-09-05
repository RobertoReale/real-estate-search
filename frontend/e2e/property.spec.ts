/** Opening one property and reading it: the click every other feature exists
 *  to lead to. */
import { checkScreen, expect, test } from "./fixtures";
import { cards, waitForResults } from "./harness/dashboard";

test("a property opens, shows its price and its listings, and closes", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";
  expect(title).not.toBe("");
  const price = await card.getByText(/^€[\d.,]+$/).innerText();

  await card.click();

  // The detail carries the same property, at the same price: a modal that
  // opened the wrong row, or re-rounded the number, would read as plausible.
  const detail = page.getByRole("heading", { level: 2, name: title });
  await expect(detail).toBeVisible();
  await expect(page.getByText(price, { exact: true }).first()).toBeVisible();

  // …and its provenance. Every demo property has at least one ad behind it, and
  // the merged ones have two — the whole reason the dashboard exists.
  const listings = page.getByRole("heading", { name: /^Found listings \(\d+\)$/ });
  await expect(listings).toBeVisible();
  const found = Number((await listings.innerText()).replace(/\D/g, ""));
  expect(found).toBeGreaterThan(0);
  await expect(page.getByRole("link", { name: /Open/ })).toHaveCount(found);

  await checkScreen(page, "the property detail");

  await page.getByRole("button", { name: "Close" }).click();
  await expect(detail).toBeHidden();
  await expect(cards(page).first()).toBeVisible();
});
