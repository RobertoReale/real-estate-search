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

  // The detail carries the same property, at the same price: a screen that
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

test("j, k and the arrows walk the results without leaving the property", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await cards(page).nth(1).click();

  const at = () => new URL(page.url()).pathname;
  const position = page.getByText(/^\d+ of \d+$/);
  await expect(position).toHaveText(/^2 of \d+$/);
  const second = at();

  // Forward and back, on both sets of keys. Each one is a whole navigation —
  // the address changes and the property under it changes — and none of them
  // takes the reader back to the grid on the way.
  for (const [forward, back] of [["j", "k"], ["ArrowRight", "ArrowLeft"]] as const) {
    await page.keyboard.press(forward);
    await expect(position).toHaveText(/^3 of \d+$/);
    expect(at()).not.toBe(second);
    await page.keyboard.press(back);
    await expect(position).toHaveText(/^2 of \d+$/);
    expect(at()).toBe(second);
  }

  // …and a "j" typed into the notes is a letter, not a navigation. This is the
  // whole reason the shortcut is not simply bound to the window.
  const notes = page.locator("[data-action='detail.notes']");
  await notes.fill("just a note");
  await expect(notes).toHaveValue("just a note");
  expect(at()).toBe(second);
  await page.locator("h2").first().click();

  // The first result has nothing before it, and says so rather than wrapping
  // round to the last one.
  await page.keyboard.press("k");
  await expect(position).toHaveText(/^1 of \d+$/);
  await page.keyboard.press("k");
  await expect(position).toHaveText(/^1 of \d+$/);
});
