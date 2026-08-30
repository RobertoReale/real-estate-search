/** How a journey reaches the app as a brand-new user meets it.
 *
 *  Onboarding is the one screen the seeded corpus cannot show: it appears only
 *  while no monitored search exists, and creating one is a door that does not
 *  open again — nothing in the app puts a database back to never-having-had-a
 *  search. Running the journey against the seeded backend would therefore mean
 *  faking the two answers it turns on, which is a test of the fake.
 *
 *  So the harness starts a second backend on an empty data directory
 *  (playwright.config.ts), and this points one page's `/api` calls at it. The
 *  browser still asks the preview origin, so the app is served, built and
 *  same-origin exactly as in every other journey; only the database behind the
 *  answers is different, and it is a real one.
 */
import type { Page } from "@playwright/test";
import { EMPTY_BACKEND_ORIGIN } from "./ports";

/** Redirects this page's API calls to the empty backend, for the rest of the
 *  test. Page routes are matched before the context-wide offline guard, so the
 *  guard never sees these and nothing here weakens it. */
export async function useEmptyBackend(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const { pathname, search } = new URL(route.request().url());
    const response = await route.fetch({ url: `${EMPTY_BACKEND_ORIGIN}${pathname}${search}` });
    await route.fulfill({ response });
  });
}
