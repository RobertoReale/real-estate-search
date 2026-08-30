/** The first screen anyone ever sees: nothing collected yet, and what to do.
 *
 *  Against a genuinely empty database (see harness/empty.ts), because this state
 *  is unreachable once a search exists and a stubbed answer would only prove the
 *  stub.
 */
import { checkScreen, expect, test } from "./fixtures";
import { useEmptyBackend } from "./harness/empty";
import { cards } from "./harness/dashboard";

test("a first run says what to do instead of showing an empty page", async ({ page }) => {
  await useEmptyBackend(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Real Estate Search" })).toBeVisible();
  await expect(cards(page)).toHaveCount(0);

  // The three steps, present and in order. A blank dashboard with no
  // instructions is indistinguishable from a broken one.
  await expect(page.getByText("Welcome! Three steps to get started:")).toBeVisible();
  const steps = page.getByRole("listitem");
  await expect(steps).toHaveCount(3);
  await expect(steps.nth(0)).toContainText("Add a search above");
  await expect(steps.nth(1)).toContainText("Start Scan Now");
  await expect(steps.nth(2)).toContainText("Settings");

  // …and step one is actionable from here: all three ways to create a search
  // are on this screen, not behind a menu the text does not mention.
  for (const way of ["💬 Just describe it", "🧭 Build a search", "🔗 Paste a URL"]) {
    await expect(page.getByRole("button", { name: way })).toBeVisible();
  }

  await checkScreen(page, "the first-run screen");
});
