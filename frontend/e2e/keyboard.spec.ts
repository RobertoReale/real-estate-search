/** The dashboard driven with the hands off the mouse.
 *
 *  Every other spec clicks. This one is the axis nothing else covers: what a
 *  keyboard reaches, what it can see it has reached, and the four keys that make
 *  reading a hundred results bearable without a pointer. The rule the whole file
 *  rests on is that focus is asserted through `document.activeElement` after a
 *  *real* key press — a `.focus()` from the harness would prove the element
 *  exists and nothing about whether a user can get to it.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, waitForResults } from "./harness/dashboard";
import type { Page } from "@playwright/test";

/** The inventory id of whatever holds the focus, which is how this file names
 *  the thing a key landed on. */
function focusedAction(page: Page): Promise<string | null> {
  return page.evaluate(() =>
    document.activeElement?.closest<HTMLElement>("[data-action]")?.dataset.action ?? null);
}

/** The property the focus is inside, by the id the card and the map share. */
function focusedCard(page: Page): Promise<string | null> {
  return page.evaluate(() =>
    document.activeElement?.closest<HTMLElement>("[data-property-id]")?.dataset.propertyId ?? null);
}

/** Two frames: long enough for a shortcut that was going to move the focus to
 *  have moved it, which is what an assertion that it did *not* has to allow. */
function settle(page: Page): Promise<void> {
  return page.evaluate(() => new Promise<void>((done) =>
    requestAnimationFrame(() => requestAnimationFrame(() => done()))));
}

test("the first Tab is a way past the header, and it shows itself", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // Nothing is focused on a fresh load, so the first Tab lands on the first
  // focusable element in the document — which has to be this one. Behind it are
  // the brand, four destinations and four header buttons, paid for again on
  // every screen by anyone who cannot use a mouse.
  await page.keyboard.press("Tab");
  expect(await focusedAction(page)).toBe("nav.skipToContent");

  // All of it inside the viewport: it is parked above the top edge until it has
  // focus, and a link that stays parked is one a screen reader announces and
  // nobody can see. Awaited rather than measured once — it slides in, and the
  // frame the key lands on is not the frame it arrives.
  const link = page.locator("[data-action='nav.skipToContent']");
  await expect(link).toBeInViewport({ ratio: 1 });

  // On screen, it is a control like any other and is held to the same contrast
  // and layout rules at the three widths.
  await checkScreen(page, "the skip link with the focus on it");

  await page.keyboard.press("Enter");
  // The focus moves, not only the scroll position: an anchor that moved the
  // reading position alone would send the very next Tab back into the header
  // the user just skipped.
  expect(await page.evaluate(() => document.activeElement?.id)).toBe("main");
});

test("/ puts the caret in the keyword box, at both shapes of the rail", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // Awaited rather than read once: the box may have to be put on screen before
  // it can be focused, and the focus lands on the frame after the key.
  const box = page.locator("[data-action='filters.query']");
  await page.keyboard.press("/");
  await expect(box).toBeFocused();

  // The key is not a character once the caret is in a field: a second `/` is a
  // slash typed into the box, which is what a user searching for "via 24/A"
  // needs it to be.
  await page.keyboard.type("attico/2");
  await expect(box).toHaveValue("attico/2");

  // On a phone the rail is behind a toggle, and the key has to open it before
  // there is a box to type in — otherwise the shortcut works only where the
  // pointer already made it unnecessary.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await waitForResults(page);
  await expect(box).toBeHidden();

  await page.keyboard.press("/");
  await expect(box).toBeVisible();
  // The sheet takes the focus for itself as it opens, so this is also the
  // assertion that the shortcut lands *after* it and not under it.
  await expect(box).toBeFocused();
});

test("j and k walk the results and f stars the one under the focus", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  const ids = await cards(page).evaluateAll((els) =>
    els.map((el) => (el as HTMLElement).dataset.propertyId ?? ""));
  expect(ids.length).toBeGreaterThan(2);

  // From nothing focused, `j` starts at the top rather than doing nothing.
  await page.keyboard.press("j");
  expect(await focusedCard(page)).toBe(ids[0]);
  // …and it lands on the control that opens the property, so Enter reads on
  // from where the walking stopped.
  expect(await focusedAction(page)).toBe("property.open");

  await page.keyboard.press("j");
  expect(await focusedCard(page)).toBe(ids[1]);
  await page.keyboard.press("k");
  expect(await focusedCard(page)).toBe(ids[0]);

  // The top of the list has nothing above it, and the key is left to the page
  // rather than swallowed: the focus stays where it was.
  await page.keyboard.press("k");
  expect(await focusedCard(page)).toBe(ids[0]);

  // `f` is the quick action of the card the focus is in, and of no other.
  const star = cards(page).first().locator("[data-action='property.favorite']");
  const before = await star.getAttribute("aria-label");
  await page.keyboard.press("f");
  await expect(star).not.toHaveAttribute("aria-label", before ?? "");
  await page.keyboard.press("f");
  await expect(star).toHaveAttribute("aria-label", before ?? "");
});

test("the shortcuts stop at the edge of a screen that is covering the grid", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  // Settings is a screen drawn over the grid, and the grid stays mounted behind
  // it. A bare key that reached through would pull the focus out from under
  // what the user is reading and into a list they cannot see.
  await page.locator("[data-action='nav.settings']").click();
  await expect(page.locator("[data-action='settings.save']")).toBeVisible();

  await page.keyboard.press("/");
  await page.keyboard.press("j");
  // Two frames, which is longer than either key would take to land if it were
  // going to: the negative has to be given the chance to fail.
  await settle(page);
  expect(await focusedAction(page)).not.toBe("filters.query");
  expect(await focusedCard(page)).toBeNull();
});

test("Esc closes the property, in both shapes it opens in", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await waitForResults(page);

  const title = (await cards(page).first().getAttribute("aria-label")) ?? "";
  await cards(page).first().click();
  const detail = page.getByRole("heading", { level: 2, name: title });
  await expect(detail).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(detail).toBeHidden();
  await expect(cards(page).first()).toBeVisible();

  // …and closing is a step back, not a fork in the history: the same press must
  // not leave a duplicate entry for Back to walk through.
  await page.goBack();
  await expect(detail).toBeVisible();

  // Below `lg` the detail is a sheet, and the key belongs to the sheet. It is
  // asserted here because a window-level handler added on top of it would close
  // the sheet *and* navigate, which is invisible until Back stops working.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await waitForResults(page);
  await cards(page).first().click();
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeHidden();
  await expect(cards(page).first()).toBeVisible();
});
