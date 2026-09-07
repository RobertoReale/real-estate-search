/** The first screen anyone ever sees, and the whole walk from it to a working
 *  search.
 *
 *  Against a genuinely empty database (see harness/empty.ts), because this state
 *  is unreachable once a search exists and a stubbed answer would only prove the
 *  stub. The search this creates is a real one, saved into that throwaway
 *  database — the acceptance for the guide is that a fresh install *reaches* a
 *  created profile, and a test that stopped at the form would be checking that
 *  the form renders.
 *
 *  Nothing here reads a label out of the documentation, which is the point: the
 *  assertions are the sentences a user meets on the screen, in the order they
 *  meet them, and every step forward is a control rather than an instruction.
 */
import { checkScreen, expect, test } from "./fixtures";
import { useEmptyBackend } from "./harness/empty";
import { cards } from "./harness/dashboard";
import { control, fill, press } from "./harness/drive";

/** What the backend says while a scan is in flight. Stubbed, because a real
 *  first scan is minutes of network the browser suite is forbidden from doing —
 *  what is under test is that the screen turns this into something readable, not
 *  that the scanner works. */
const SCANNING = {
  running: true,
  last_started_at: "2026-01-01T09:00:00Z",
  last_finished_at: null,
  last_summary: "",
  next_auto_run: null,
  paused: false,
  data_version: "first-run",
  progress: {
    active: true, phase: "fetching", detail: "", profile: "First search",
    profile_index: 1, profile_total: 1, portal: "immobiliare",
    page: 2, total_pages: null, listings: 17, total_listings: null,
    transport: "http", waiting_seconds: 0,
  },
};

const path = (page: { url(): string }) => new URL(page.url()).pathname;

test("a fresh install walks from nothing to a created search", async ({ page }) => {
  await useEmptyBackend(page);

  // ── the bare address, on a database that has never held a search ──────────
  await page.goto("/");
  await expect.poll(() => path(page)).toBe("/start");
  await expect(page.getByRole("heading", { name: "Ricerca Immobili" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Come iniziare" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Controlla i portali al posto tuo" }),
  ).toBeVisible();
  await checkScreen(page, "the guided first run, step one");

  // ── leaving is a decision, and it is remembered ───────────────────────────
  await press(page, "onboarding.skip");
  await expect.poll(() => path(page)).toBe("/listings");
  await expect(cards(page)).toHaveCount(0);
  await expect(page.getByText("Non è ancora stato raccolto nulla.")).toBeVisible();
  // With nothing collected there is nothing to narrow, and every control in the
  // rail would describe a set that does not exist. Worse, a form of price and
  // rooms and zone on an empty screen reads as the place a search is set up —
  // which is the misunderstanding this whole screen exists to prevent. So the
  // rail is not on it, and the one useful thing is.
  await expect(page.locator('[data-action^="filters."]')).toHaveCount(0);
  await expect(control(page, "app.addSearch")).toBeVisible();
  await checkScreen(page, "the listings, before anything has been collected");

  // The bare address again. A user who said "not now" must not meet the guide
  // on every visit — this is the one assertion that the flag is written on
  // skipping rather than on finishing.
  await page.goto("/");
  await expect.poll(() => path(page)).toBe("/listings");

  // ── the other screen with nothing on it ───────────────────────────────────
  // Three panels each reporting the same absence separately would be three ways
  // of saying "no searches yet", so the screen says it once and offers the one
  // thing that fixes it.
  await press(page, "nav.insights");
  await expect(page.getByRole("heading", { name: "Non c'è ancora niente da analizzare" })).toBeVisible();
  await checkScreen(page, "insights with nothing collected");
  await press(page, "insights.toSearches");
  await expect.poll(() => path(page)).toBe("/searches");

  // ── back into the guide, from the screen it fills in ──────────────────────
  await press(page, "nav.listings");
  await press(page, "app.addSearch");
  await expect.poll(() => path(page)).toBe("/start");

  // Forward, back, forward: a step reconsidered costs one click and loses
  // nothing, which is what makes the first of them safe to read past.
  await press(page, "onboarding.next");
  await expect(
    page.getByRole("heading", { name: "Crea la tua prima ricerca" }),
  ).toBeVisible();
  await press(page, "onboarding.back");
  await expect(
    page.getByRole("heading", { name: "Controlla i portali al posto tuo" }),
  ).toBeVisible();
  await press(page, "onboarding.next");

  // ── the three ways, as one choice ─────────────────────────────────────────
  for (const way of ["Descrivila e basta", "Costruisci una ricerca", "Incolla un URL"]) {
    await expect(page.getByRole("button", { name: new RegExp(way) })).toBeVisible();
  }
  await checkScreen(page, "the first search, offered as one choice");

  // Each of them opens where it says it does, and each is one click from the
  // other two — a wrong first pick must not be a dead end.
  await press(page, "onboarding.wayAssistant");
  await expect(control(page, "profiles.assistant.query")).toBeVisible();
  await press(page, "onboarding.wayBack");

  await press(page, "onboarding.wayBuilder");
  await expect(control(page, "profiles.builder.city")).toBeVisible();
  await press(page, "onboarding.wayBack");

  // ── and one of them actually creates a search ─────────────────────────────
  // The URL way, because it is the only one of the three that needs no network:
  // the assistant asks a model and the builder asks the portals, and this suite
  // is offline by construction.
  await press(page, "onboarding.wayUrl");
  await expect(page.getByText(/per usare tutti i filtri del portale/)).toBeVisible();
  await fill(page, "profiles.url.name", "First search");
  await fill(page, "profiles.url.url",
    "https://www.immobiliare.it/vendita-case/milano/?criterio=rilevanza&prezzoMassimo=400000");
  await press(page, "profiles.url.save");

  // Saving is what unlocks the last step, and it opens it rather than announcing
  // that it could be opened.
  await expect(page.getByText("La tua ricerca è salvata.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Avvia la prima scansione" })).toBeVisible();
  await checkScreen(page, "the first scan, with a search to run it on");

  // ── the scan, and something to look at while it runs ──────────────────────
  await page.route("**/api/scrapers/trigger", (route) =>
    route.fulfill({ json: { status: "started" } }));
  await page.route("**/api/scrapers/status", (route) => route.fulfill({ json: SCANNING }));

  await press(page, "onboarding.scan");
  // A count that rises and a phase in words. Never a proportion: the portals
  // declare no total here, and a bar that fills to 90% and stops is a lie the
  // shape of the payload exists to prevent.
  await expect(page.getByText("Lettura dei risultati, pagina 2")).toBeVisible();
  await expect(page.getByText("17 raccolti finora")).toBeVisible();
  await expect(page.getByText(/%/)).toHaveCount(0);

  // ── out, onto the screen the app opens on from now on ─────────────────────
  await press(page, "onboarding.done");
  await expect.poll(() => path(page)).toBe("/listings");
});
