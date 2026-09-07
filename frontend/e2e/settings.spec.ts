/** The two per-device choices, and the dialog everything else is configured in.
 *
 *  Language and theme are stored per browser rather than on the server, which is
 *  exactly why they need a browser test: nothing in the backend suite can say
 *  whether a reload keeps them.
 */
import { checkScreen, expect, test } from "./fixtures";
import { resultCount, waitForResults } from "./harness/dashboard";
import { press } from "./harness/drive";

test("Settings opens over the grid and closes back to it", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // One of the four places in the navigation, so it is a link rather than a
  // button — but a dialog over the listings rather than a screen beside them,
  // which is what the rest of this journey is about.
  await press(page, "nav.settings");
  await expect(page.getByRole("heading", { name: "Impostazioni" })).toBeVisible();
  // Loaded, not merely opened: the dialog cannot render a field until the
  // backend answers, and a failed load used to leave it blank.
  await expect(page.getByRole("button", { name: "Salva le impostazioni" })).toBeVisible();
  await checkScreen(page, "the settings dialog");

  await page.getByRole("button", { name: "Chiudi" }).first().click();
  await expect(page.getByRole("heading", { name: "Impostazioni" })).toBeHidden();
  await waitForResults(page);
});

test("switching language repaints the grid, and the choice survives a reload", async ({
  page,
}) => {
  await page.goto("/");
  await waitForResults(page);
  const count = await resultCount(page);

  // Nothing was chosen and nothing was stored, so this is the language the app
  // opens in — an Italian product does not ask the browser what it prefers.
  await expect(page.locator("html")).toHaveAttribute("lang", "it");
  await expect(page.getByText(`${count} immobili`)).toBeVisible();

  // The switch is in the shell rather than inside Settings — two languages
  // make a toggle, and it has to survive a 390px header. One press, from the
  // grid, without opening anything: that is what keeps English a language the
  // app speaks rather than one it used to.
  await page.getByRole("button", { name: "Passa a English" }).click();

  await expect(page.getByText(`${count} properties`)).toBeVisible();
  // The count alone would also be satisfied by a number that never moved, so a
  // second string: a filter the user types into, on this screen rather than in
  // the shell around it.
  await expect(page.getByLabel(/^Max price €/)).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await checkScreen(page, "the grid in English");

  // The reload is the whole point of the switch. Italian is a default, and a
  // default that survives a choice made against it is a lock: what was stored
  // wins here, or English is unreachable for anyone who ever closes the tab.
  await page.reload();
  await waitForResults(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByText(`${count} properties`)).toBeVisible();

  // The way back is labelled in English too — the switch describes itself in
  // the language currently on screen, not in the one it leads to.
  await page.getByRole("button", { name: "Switch to Italiano" }).click();
  await expect(page.getByText(`${count} immobili`)).toBeVisible();
});

test("the theme toggle survives a reload", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  const html = page.locator("html");
  await expect(html).not.toHaveClass(/dark/);

  await page.getByRole("button", { name: "Passa al tema scuro" }).click();
  await expect(html).toHaveClass(/dark/);
  await checkScreen(page, "the grid in the dark theme");

  await page.reload();
  await waitForResults(page);
  await expect(html).toHaveClass(/dark/);
  await expect(page.getByRole("button", { name: "Passa al tema chiaro" })).toBeVisible();

  await page.getByRole("button", { name: "Passa al tema chiaro" }).click();
  await expect(html).not.toHaveClass(/dark/);
});
