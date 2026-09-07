/** What the app says it cannot do, and where it says it.
 *
 *  The rule under test is not "the sentence is on the screen" — a translation
 *  string would satisfy that and would then quietly lie the first time someone
 *  changed the setting behind it. It is **the number in the sentence is the
 *  backend's number**. So every figure asserted here is one the harness backend
 *  would never produce on its own: a page cap of 3 rather than 10, a portal
 *  total of 812, eleven days rather than seven, thirty listings a request
 *  rather than fifty. If any of those came from the copy, the copy would print
 *  the old value and the assertion would fail.
 *
 *  `docs/limits.md` is the full inventory; this is a sample of it, chosen for
 *  the three shapes a limit can take — one read straight off a response, one
 *  computed from a published constant and a value the user is editing, and one
 *  that has to reach a card through the grid.
 *
 *  The last test is the other half of the rule, and the one most likely to rot:
 *  a limit is a fact, not a warning. Only two of them mean *the answer in front
 *  of you is incomplete* — a portal that refused, and a search that stopped at
 *  the cap — and only those two are allowed to be coloured like it.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, waitForResults } from "./harness/dashboard";
import { fill, press } from "./harness/drive";
import { fakeEventStream } from "./harness/stream";

import type { Locator, Page } from "@playwright/test";

/** A limit by name, wherever on the page it was stated. */
const limit = (page: Page, id: string): Locator => page.locator(`[data-limit="${id}"]`);

/** Two finished searches with the qualifications that matter: one stopped at
 *  the cap with the portal's own total known, one refused outright. The numbers
 *  are deliberately not the defaults — `max_pages_per_search` ships at 10. */
const JOURNAL = [
  {
    profile_id: 1, profile: "Trilocale Navigli", portal: "immobiliare",
    started_at: "2026-03-04T10:00:00Z", finished_at: "2026-03-04T10:03:10Z",
    pages: 3, listings: 74, outcome: "ok", detail: "", transport: "http",
    stopped_because: "", mode: "full",
    truncated: true, page_limit: 3, total_listings: 812, outside_area: 9,
  },
  {
    profile_id: 2, profile: "Bilocale Isola", portal: "idealista",
    started_at: "2026-03-04T10:04:00Z", finished_at: "2026-03-04T10:06:30Z",
    pages: 0, listings: 0, outcome: "blocked", detail: "", transport: "browser",
    stopped_because: "the portal returned a challenge page", mode: "full",
    truncated: false, page_limit: 3, total_listings: null, outside_area: 0,
  },
];

async function fakeJournal(page: Page): Promise<void> {
  await page.route("**/api/scans/journal", (route) => route.fulfill({ json: JOURNAL }));
}

/** Rewrites part of a real answer, so everything not under test stays whatever
 *  the backend actually said and cannot drift out of shape. */
async function patched(
  page: Page,
  matches: (url: URL) => boolean,
  edit: (body: Record<string, unknown>) => Record<string, unknown>,
): Promise<void> {
  await page.route(matches, async (route) => {
    try {
      const response = await route.fetch();
      await route.fulfill({ json: edit(await response.json()) });
    } catch {
      // the page went away while this was in the air
    }
  });
}

test("a scan that did not finish says so with its own cap and the portal's own total", async ({ page }) => {
  await fakeJournal(page);
  await page.goto("/activity");

  // The cap is 3 here and 10 everywhere else, and the total is a number no
  // scan in this suite ever collected: both can only have come off the entry.
  await expect(limit(page, "scan.pageCap")).toContainText("pagina 3");
  await expect(limit(page, "scan.pageCap")).toContainText("812");

  // The count of what came back from outside the requested area, on the row
  // that collected it — the journal is per portal, and so is the miss.
  await expect(limit(page, "scan.outsideArea")).toContainText("9");

  // A blocked search is the other kind of incomplete: nothing was collected,
  // and the reason is not that there was nothing there.
  await expect(limit(page, "scan.portalBlocked")).toBeVisible();

  await checkScreen(page, "the journal, qualified");
});

test("what an Idealista page is worth is multiplied out, never written down", async ({ page }) => {
  // Fifty is the real page size, so a copy that hardcoded it would still look
  // right. Thirty is not, which is the point of choosing it.
  await patched(page, (url) => url.pathname === "/api/settings",
    (body) => ({ ...body, idealista_api_page_size: 30, idealista_api_max_pages: 4 }));

  await page.goto("/");
  await waitForResults(page);
  await press(page, "nav.settings");

  await expect(limit(page, "settings.idealistaReach")).toContainText("4 richiesta");
  await expect(limit(page, "settings.idealistaReach")).toContainText("120");

  // …and it follows the box, not the saved value: the sentence is what the
  // field currently says it will cost, before anything is saved.
  await fill(page, "settings.scraping.idealistaMaxPages", "2");
  await expect(limit(page, "settings.idealistaReach")).toContainText("60");
});

test("a listing called gone says how many days of silence that took", async ({ page }) => {
  // Both halves of where the status arrives from — the poll and the stream —
  // or the number flips back to the backend's seven within a reconnection.
  const stream = await fakeEventStream(page);
  stream.push({ gone_after_days: 11 });
  await patched(page, (url) => url.pathname === "/api/scrapers/status",
    (body) => ({ ...body, gone_after_days: 11 }));

  // One listing forced into both states at once: no longer turning up, and
  // returned for an area the search did not ask for.
  await patched(page, (url) => url.pathname === "/api/properties", (body) => {
    const items = body.items as Record<string, unknown>[];
    return {
      ...body,
      items: items.map((item, i) =>
        i === 0 ? { ...item, status: "gone", outside_requested_area: true } : item),
    };
  });

  await page.goto("/");
  await waitForResults(page);
  const card = cards(page).first();

  await expect(card.locator('[data-limit="card.outsideArea"]')).toBeVisible();
  // The deduction and its threshold: "gone" is what a run concludes after this
  // many days, and the number belongs to the run rather than to the sentence.
  await expect
    .poll(() => card.locator('[data-limit="card.goneAfter"]').getAttribute("title"))
    .toContain("11 giorni");
});

test("only the two limits that mean the answer is incomplete are coloured like it", async ({ page }) => {
  await fakeJournal(page);
  await page.goto("/activity");
  await expect(limit(page, "scan.pageCap")).toBeVisible();

  // Twelve caution-coloured lines would teach the eye to skip the one that
  // matters, so the tone is spent on exactly the two that earn it.
  const alarming = ["scan.pageCap", "scan.portalBlocked"];
  for (const id of alarming) {
    await expect(limit(page, id)).toHaveClass(/text-caution-ink/);
  }
  await expect(limit(page, "scan.outsideArea")).not.toHaveClass(/text-caution-ink/);
});
