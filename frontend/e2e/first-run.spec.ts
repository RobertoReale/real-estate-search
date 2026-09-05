/** The first screen anyone ever sees: nothing collected yet, and what to do.
 *
 *  Against a genuinely empty database (see harness/empty.ts), because this state
 *  is unreachable once a search exists and a stubbed answer would only prove the
 *  stub.
 */
import { checkScreen, expect, test } from "./fixtures";
import { useEmptyBackend } from "./harness/empty";
import { cards } from "./harness/dashboard";
import { press } from "./harness/drive";

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
  await expect(steps.nth(0)).toContainText("Add a search under Searches");
  await expect(steps.nth(1)).toContainText("Start Scan Now");
  await expect(steps.nth(2)).toContainText("Settings");

  await checkScreen(page, "the first-run screen");

  // …and step one is a control, not only a sentence. The searches are a screen
  // of their own, so what the text names has to be one click away — an
  // onboarding step a user has to go and find is one they do not take.
  await press(page, "app.addSearch");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/searches");

  // All three ways to create a search are on it, not behind a menu.
  for (const way of ["Just describe it", "Build a search", "Paste a URL"]) {
    await expect(page.getByRole("button", { name: way })).toBeVisible();
  }

  await checkScreen(page, "the searches, reached from the first-run steps");

  // Insights before there is anything to analyse. Three panels each reporting
  // the same absence separately would be three ways of saying "no searches
  // yet", so the screen says it once and offers the one thing that fixes it.
  await press(page, "nav.insights");
  await expect(page.getByRole("heading", { name: "Nothing to analyse yet" })).toBeVisible();
  await checkScreen(page, "insights with nothing collected");
  await press(page, "insights.toSearches");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/searches");
});
