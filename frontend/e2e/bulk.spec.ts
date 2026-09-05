/** Acting on several properties at once.
 *
 *  The bar's promise is in its labels — "Hide selected (2)" has to hide two, and
 *  "Select all (n of N)" has to mean the whole filtered set rather than the page
 *  on screen. Both have been wrong here before (`pruneSelection` in App.tsx
 *  records what that cost), so both are asserted.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";

test("several properties can be selected and hidden in one action", async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept());

  await page.goto("/");
  await waitForResults(page);
  const before = await resultCount(page);

  await page.getByRole("button", { name: "Select multiple properties" }).click();

  // "Select all" means the whole filtered set the count claims, not whatever
  // the grid happens to have loaded. The name carries the tally, which is also
  // what tells this checkbox apart from the monitored-searches one above it.
  // Clicked rather than `check()`ed: the box asks the backend for the whole set
  // before it can tick, so its state lags the click by a request and Playwright
  // reads the unticked box back as a click that did nothing.
  await page.getByRole("checkbox", { name: /^Select all \(/ }).click();
  await expect(page.getByRole("checkbox", { name: `Select all (${before} of ${before})` }))
    .toBeChecked();
  await page.getByRole("checkbox", { name: /^Select all \(/ }).click();
  await expect(page.getByRole("checkbox", { name: /^Select all \(0 of/ })).not.toBeChecked();

  const chosen: string[] = [];
  for (const index of [0, 1]) {
    const card = cards(page).nth(index);
    chosen.push((await card.getAttribute("aria-label")) ?? "");
    // By tooltip: the card's tick box carries only a drawing, so its title is the
    // only thing naming it. (That it has no accessible label is one of the
    // findings this suite reports — see the axe results.)
    await card.getByTitle("Select for batch check").click();
  }
  await checkScreen(page, "the grid in selection mode");

  await page.getByRole("button", { name: "Hide selected (2)" }).click();

  // The count is the backend's: the bulk action refreshes rather than editing
  // the grid in place, so this is what the database now holds.
  await expect.poll(() => resultCount(page)).toBe(before - 2);
  for (const title of chosen) {
    await expect(page.locator("article", { hasText: title })).toBeHidden();
  }

  // Selection mode closes with the action, so the next click is an ordinary one
  // rather than a silent selection.
  await expect(page.getByRole("button", { name: "Select multiple properties" }))
    .toBeVisible();
});
