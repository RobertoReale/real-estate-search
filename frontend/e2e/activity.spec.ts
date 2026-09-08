/** The account of a scan: while it runs, and once it is over.
 *
 *  A scan reaches the portals, which this suite may not, so what the backend
 *  would be saying is served from the test (`harness/stream.ts` says why that is
 *  the honest way round). What is under test is not the scanner — it is the
 *  screen: that it names the search and the portal rather than the word
 *  "scanning", that the counts move, that the pause is called a pause, and that
 *  none of it survives into a claim the backend never made.
 *
 *  The last part is the one worth being strict about, and it has its own test:
 *  a determinate bar is a promise about how much is left, and most portals never
 *  say. A bar that fills to 90% and stops is the failure this screen was written
 *  to avoid, so the assertion is on the ARIA role rather than on a class — the
 *  role is the promise, and it is either made or it is not.
 */
import { checkScreen, expect, test } from "./fixtures";
import { waitForResults } from "./harness/dashboard";
import { control, press } from "./harness/drive";
import { fakeEventStream } from "./harness/stream";

import type { Page } from "@playwright/test";

/** A scan in flight on a portal that declared no page total — the common case,
 *  and the one the "no proportion without a total" rule exists for. */
const RUNNING = {
  running: true,
  last_started_at: "2026-03-04T10:00:00Z",
  last_finished_at: null,
  last_summary: "",
  next_auto_run: null,
  paused: false,
  progress: {
    active: true, phase: "fetching", detail: "", profile: "Trilocale Navigli",
    profile_index: 1, profile_total: 3, portal: "immobiliare",
    page: 2, total_pages: null, listings: 17, total_listings: null,
    transport: "http", waiting_seconds: 0,
  },
};

/** Two finished searches, one of which did not work. The journal is the only
 *  thing on this screen that outlives the scan, so it is the only thing the
 *  reload test can assert on. */
const JOURNAL = [
  {
    profile_id: 2, profile: "Bilocale Isola", portal: "idealista",
    started_at: "2026-03-04T10:04:00Z", finished_at: "2026-03-04T10:06:30Z",
    pages: 3, listings: 0, outcome: "blocked", detail: "",
    transport: "browser", stopped_because: "the portal returned a challenge page",
    mode: "full",
  },
  {
    profile_id: 1, profile: "Trilocale Navigli", portal: "immobiliare",
    started_at: "2026-03-04T10:00:00Z", finished_at: "2026-03-04T10:03:10Z",
    pages: 4, listings: 41, outcome: "ok", detail: "", transport: "http",
    stopped_because: "", mode: "full",
  },
];

/** The journal, answered from here: the harness database has never had a scan,
 *  and an empty list would only prove the empty state. */
async function fakeJournal(page: Page, entries: unknown[] = JOURNAL): Promise<void> {
  await page.route("**/api/scans/journal", (route) => route.fulfill({ json: entries }));
}

/** Pressing "Scan now" is a real press; only what it asks for is answered here. */
async function fakeTrigger(page: Page): Promise<void> {
  await page.route("**/api/scrapers/trigger", (route) =>
    route.fulfill({ json: { status: "started" } }));
}

const path = (page: Page) => new URL(page.url()).pathname;

test("a running scan says which search, on which portal, and how much has come back", async ({ page }) => {
  const stream = await fakeEventStream(page);
  await fakeJournal(page);
  await fakeTrigger(page);

  await page.goto("/");
  await waitForResults(page);

  // The header button is the way in, and what it opens is this rather than the
  // backend log — the log is a developer's answer to a user's question.
  await press(page, "nav.activity");
  await expect.poll(() => path(page)).toBe("/activity");
  await expect(page.getByRole("heading", { name: "Nessuna scansione in corso" })).toBeVisible();

  await press(page, "activity.scan");
  stream.push(RUNNING);

  await expect(page.getByRole("heading", { name: "Scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });
  await expect(control(page, "activity.scan")).toBeDisabled();

  // Which search, of how many, and where — the three facts the word "scanning"
  // was standing in for.
  await expect(page.getByText("Trilocale Navigli").first()).toBeVisible();
  await expect(page.getByText("Ricerca 1 di 3")).toBeVisible();
  await expect(page.getByText("immobiliare", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Lettura dei risultati, pagina 2")).toBeVisible();
  await expect(page.getByText("Trasporto:")).toBeVisible();
  await expect(page.getByText("http", { exact: true })).toBeVisible();
  await expect(page.getByText("17 annunci raccolti finora")).toBeVisible();

  await checkScreen(page, "a scan in flight");

  // …and it rises, which is the whole reason to sit and watch it.
  stream.push({
    ...RUNNING,
    progress: { ...RUNNING.progress, page: 5, listings: 63, transport: "browser" },
  });
  await expect(page.getByText("63 annunci raccolti finora")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Lettura dei risultati, pagina 5")).toBeVisible();
  // The ladder escalated, and the point of showing the transport is that this
  // is visible when it happens rather than afterwards in the log.
  await expect(page.getByText("browser", { exact: true })).toBeVisible();

  // Where most of a scan's time actually goes, named as what it is. A user who
  // reads a still screen as a crashed one is the reason this line exists.
  stream.push({
    ...RUNNING,
    progress: { ...RUNNING.progress, phase: "waiting", waiting_seconds: 6 },
  });
  await expect(page.getByText("Pausa di 6s prima della pagina successiva"))
    .toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/La pausa è voluta/)).toBeVisible();
});

test("the journal is still readable after the scan ends, and after a reload", async ({ page }) => {
  const stream = await fakeEventStream(page);
  await fakeJournal(page);
  stream.push(RUNNING);

  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });

  // Each portal's outcome as it lands, not all at the end: the failed search is
  // already in the journal while the next one is still being read.
  await expect(page.getByText("Bilocale Isola")).toBeVisible();
  await expect(page.getByText("Bloccata", { exact: true })).toBeVisible();
  await expect(page.getByText("Si è fermata perché: the portal returned a challenge page."))
    .toBeVisible();
  // …and a run that simply worked spends no sentence explaining itself.
  await expect(page.getByText("4 pagine, 41 annunci")).toBeVisible();
  await expect(page.getByText("Conclusa", { exact: true })).toBeVisible();

  // The scan ends. The live panel has nothing left to say; the journal does.
  stream.push({ running: false, last_finished_at: "2026-03-04T10:06:30Z", progress: undefined });
  await expect(page.getByRole("heading", { name: "Nessuna scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Trilocale Navigli")).toBeVisible();
  await expect(page.getByText("Bilocale Isola")).toBeVisible();

  await checkScreen(page, "the activity screen with nothing running");

  // Someone who left the room comes back to a new tab. The rows come from the
  // backend, so they survive everything this one accumulated.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Le ultime scansioni" }))
    .toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Bilocale Isola")).toBeVisible();
  await expect(page.getByText("3 pagine, 0 annunci")).toBeVisible();
});

test("the scan says which portals answered, and which one did not", async ({ page }) => {
  const stream = await fakeEventStream(page);
  await fakeJournal(page, []);
  // One portal read, the other turned away. The counts elsewhere on this screen
  // cannot tell this apart from a scan that reached both: they are the same
  // numbers either way, which is the reason the line exists.
  const portals = [
    { portal: "immobiliare", attempted: 1, answered: 1, listings: 47, outcome: "ok" },
    { portal: "idealista", attempted: 1, answered: 0, listings: 0, outcome: "blocked" },
  ];
  stream.push({ ...RUNNING, last_portals: portals });

  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Immobiliare: 47 annunci · Idealista: bloccato")).toBeVisible();

  // The scan ends and the question does not: "am I looking at both sites or at
  // one?" is asked afterwards at least as often as during.
  stream.push({
    running: false, last_finished_at: "2026-03-04T10:06:30Z",
    progress: undefined, last_portals: portals,
  });
  await expect(page.getByRole("heading", { name: "Nessuna scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Immobiliare: 47 annunci · Idealista: bloccato")).toBeVisible();

  // A portal blocked part way through still hands over what it had. Both facts
  // stand together: the listings are real, and the reading behind them is not
  // finished — reporting only the count is how a partial scan reads as a whole.
  stream.push({
    running: false, last_finished_at: "2026-03-04T10:06:30Z", progress: undefined,
    last_portals: [
      { portal: "immobiliare", attempted: 3, answered: 2, listings: 47, outcome: "blocked" },
    ],
  });
  await expect(page.getByText("Immobiliare: 47 annunci (2 ricerche su 3)"))
    .toBeVisible({ timeout: 10_000 });
});

test("no proportion is drawn where the portal never declared a total", async ({ page }) => {
  const stream = await fakeEventStream(page);
  await fakeJournal(page, []);
  stream.push(RUNNING);

  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });

  // The bar is there and it is moving; what it is not is a fraction. `page: 2`
  // with no total may only ever be "Pagina 2".
  await expect(page.getByText("Pagina 2 · il portale non ha detto quante sono"))
    .toBeVisible();
  await expect(
    page.getByRole("progressbar"),
    "a determinate progress bar was rendered for a portal that declared no page "
    + "total — that bar is a promise about how much is left, and nothing had "
    + "been said that would make it true",
  ).toHaveCount(0);

  // A portal that did declare one is the other half of the rule: the bar is
  // allowed exactly here, it is named by what is progressing rather than by its
  // own running commentary, and three of eight is the 38% it says it is.
  stream.push({ ...RUNNING, progress: { ...RUNNING.progress, page: 3, total_pages: 8 } });
  const bar = page.getByRole("progressbar", { name: "Pagine lette" });
  await expect(bar).toHaveCount(1, { timeout: 10_000 });
  await expect(bar).toHaveAttribute("aria-valuenow", "38");
  await expect(page.getByText("Pagina 3 di 8")).toBeVisible();

  // Nothing has been scanned on this install, and the journal says so rather
  // than being absent — the screen has to be legible before the first scan too.
  await expect(page.getByText("Non è ancora stata fatta nessuna scansione")).toBeVisible();
});

test("a stream that cannot be opened does not turn a running scan into a finished one", async ({ page }) => {
  const stream = await fakeEventStream(page);
  await fakeJournal(page, []);
  stream.push(RUNNING);
  // The poll the fallback goes back to has to agree with what the stream was
  // saying, or this would be testing the stub rather than the fallback.
  await page.route("**/api/scrapers/status", (route) => route.fulfill({ json: RUNNING }));

  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Scansione in corso" }))
    .toBeVisible({ timeout: 10_000 });

  // Three refused opens put the timers back (B.4). The scan is still running
  // throughout, and the screen has to keep saying so — a connection this app
  // lost is not news about the scanner.
  stream.setDown(true);
  await expect(page.getByText(/l'aggiornamento avviene a intervalli/))
    .toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { name: "Scansione in corso" })).toBeVisible();
  await expect(page.getByText("Trilocale Navigli").first()).toBeVisible();
});
