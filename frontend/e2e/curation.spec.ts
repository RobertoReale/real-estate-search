/** Marking a property: the three verbs that change what the grid holds.
 *
 *  Hiding is the one destructive action reachable in a single click, and the
 *  app's answer to a misclick is not an Undo button but the Discarded filter and
 *  Restore. That round trip is the assertion here: a user who hides the wrong
 *  card has to be able to get it back, or the click is a trap.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";

test("a property can be favourited and unfavourited from the card", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";
  const favourite = card.getByRole("button", { name: "Add to favorites" });
  await favourite.click();
  await expect(card.getByRole("button", { name: "Remove from favorites" })).toBeVisible();

  // The star is a filter, not decoration: the Favorites checkbox has to find
  // what was just starred.
  await page.getByRole("checkbox", { name: "Favorites" }).check();
  await waitForResults(page);
  await expect(page.locator("article", { hasText: title })).toBeVisible();
  await checkScreen(page, "the favourites grid");

  // Unstarring while the filter is on drops the card there and then, rather
  // than leaving an empty star behind until the next background refresh.
  const starred = page.locator("article", { hasText: title });
  await starred.getByRole("button", { name: "Remove from favorites" }).click();
  await expect(starred).toBeHidden();

  await page.getByRole("checkbox", { name: "Favorites" }).uncheck();
  await waitForResults(page);
  await expect(
    page.locator("article", { hasText: title }).getByRole("button", { name: "Add to favorites" }),
  ).toBeVisible();
});

test("hiding a property takes it out of the grid, and Restore brings it back", async ({ page }) => {
  // The quick-hide asks before it acts (hiding never undoes itself), and so
  // does Restore. Playwright dismisses dialogs unless told otherwise, which
  // would make both clicks silently do nothing.
  page.on("dialog", (dialog) => dialog.accept());

  await page.goto("/");
  await waitForResults(page);
  const before = await resultCount(page);

  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";
  await card.getByRole("button", { name: "Hide this property" }).click();
  await expect(page.locator("article", { hasText: title })).toBeHidden();

  // Where a hidden property goes, and the way back from it. Changing the status
  // filter also refetches, so the count that comes back is the backend's answer
  // and not the grid's local edit. `exact` because the chip that undoes the
  // filter is labelled after it too, and `getByLabel` matches on substring.
  await page.getByLabel("Status", { exact: true }).selectOption({ label: "Discarded" });
  await waitForResults(page);
  const hidden = page.locator("article", { hasText: title });
  await expect(hidden).toBeVisible();

  await hidden.click();
  await page.getByRole("button", { name: "Restore property" }).click();
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeHidden();

  await page.getByLabel("Status", { exact: true }).selectOption({ label: "For sale" });
  await expect.poll(() => resultCount(page)).toBe(before);
  await expect(page.locator("article", { hasText: title })).toBeVisible();
});
