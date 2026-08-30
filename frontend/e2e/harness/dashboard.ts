/** The handful of things every journey needs to point at.
 *
 *  Roles and visible text throughout, never a CSS class: a class is an
 *  implementation detail that Phase C is about to rewrite wholesale, and a suite
 *  pinned to one would go red on a rename while staying blind to a button that
 *  stopped working. What a user can see and name is the stable surface.
 */
import { expect, type Locator, type Page } from "@playwright/test";

/** The property cards. `<article>` is the card's own element and nothing else in
 *  the dashboard uses it; the accessible name of each is the listing's title
 *  (`PropertyCard`, `role="button"`). */
export function cards(page: Page): Locator {
  return page.locator("article");
}

/** The result count the filter bar prints, which is the size of the whole
 *  filtered set rather than of the page loaded so far. */
export async function resultCount(page: Page): Promise<number> {
  const label = await page.getByText(/^\d+ (properties|immobili)$/).innerText();
  return Number.parseInt(label, 10);
}

/** Waits for the grid to hold something. The filter effect is debounced by
 *  250 ms and the fetch follows it, so every journey that changes a filter has
 *  to wait for the *result* rather than for the click. */
export async function waitForResults(page: Page): Promise<void> {
  await expect(cards(page).first()).toBeVisible();
}
