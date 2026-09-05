/** A.5 — every action, inventoried.
 *
 *  The other specs are journeys: they follow a user with a goal. This one has
 *  no goal. It presses everything, and then proves that "everything" is the
 *  whole of it.
 *
 *  Two gates hold it up, and they are the last two tests in the file because
 *  they judge what came before:
 *
 *  1. **No orphan handler.** A pass over `src/` (see `harness/jsx.ts`) collects
 *     every element carrying a click, change, submit or key handler and fails on
 *     one without a `data-action`, on an id the inventory does not carry, and on
 *     an inventory row no longer present in the source. Adding a button without
 *     an entry turns the build red the same day.
 *  2. **No untested action.** The recorder (`harness/recorder.ts`) writes down
 *     what the *browser* saw fired, across the whole run, and this fails on any
 *     row nothing reached. This project runs it as its own Playwright project,
 *     after the journeys, so a control a journey already exercises counts.
 *
 *  Every action in between is asserted on three axes, which is the difference
 *  between an inventory and a smoke test: it does what its row says (a visible,
 *  asserted change), it is reachable with the Tab key alone, and the app stays
 *  usable when the backend refuses the request behind it.
 *
 *  **On stubbing.** A handful of controls do something that leaves this machine
 *  — start a scan, probe a listing on the portal, open a browser at DataDome,
 *  install a package. The suite may reach nothing beyond its own two servers,
 *  so for those the *transport* is stubbed and the control is still driven for
 *  real: its handler runs, its effect renders, its failure path is exercised.
 *  That is a smaller claim than "the scan works" and it is not written up as a
 *  larger one. Exactly one control is not driven at all, and `actions.ts` says
 *  which and why.
 */
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ACTION_IDS, INVENTORY, type ActionId } from "./actions";
import { expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";
import {
  choose, control, fill, press, reachableByKeyboard, setTicked, toggle, visibleActions,
} from "./harness/drive";
import { interactiveElements, literalsInSource } from "./harness/jsx";
import { readRecordings } from "./harness/recorder";

import type { Page } from "@playwright/test";

const SRC = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src");

/* ────────────────────────── shared moves ────────────────────────── */

/** Applies something that must change how many properties the grid holds, then
 *  puts it back. The count is the filter bar's own, which is the size of the
 *  whole filtered set rather than of the page loaded so far — so this is an
 *  assertion about the backend's answer and not about the DOM. */
async function narrows(
  page: Page,
  apply: () => Promise<void>,
  restore: () => Promise<void>,
): Promise<void> {
  const before = await resultCount(page);
  await apply();
  await expect.poll(() => resultCount(page), { timeout: 15_000 }).not.toBe(before);
  await restore();
  await expect.poll(() => resultCount(page), { timeout: 15_000 }).toBe(before);
}

/** Opens the settings dialog and waits for the form rather than the shell:
 *  the shell renders while the settings are still loading. */
async function openSettings(page: Page): Promise<void> {
  await press(page, "nav.settings");
  await expect(control(page, "settings.save")).toBeVisible();
}

/** Runs something that ends in a full page reload, and returns once the app is
 *  back and ready to be pressed again.
 *
 *  The signal is the browser's own `load`, armed *before* the action so the
 *  event cannot arrive before there is anything listening for it. The obvious
 *  alternative — wait for a control to disappear — is not a signal at all but a
 *  race: it asks to observe the gap between the old document and the new one,
 *  and nothing entitles a test to see that gap. Settings is an address now, so
 *  the page comes back into the same dialog with the same buttons, and on a
 *  quick machine they are re-rendered before the next poll looks. It cost a run:
 *  the same commit passed at 21:57 and failed at 22:11 with nothing edited in
 *  between, on a `toBeHidden` that had simply blinked past. A gate that depends
 *  on how busy the machine is teaches everyone to press re-run, which is worse
 *  than one that is honestly red.
 *
 *  Every reload in this app is triggered from inside Settings, so the dialog's
 *  own Save is the postcondition: it is the last thing to render, after the
 *  settings have been fetched afresh from the process that came back.
 */
async function throughAReload(page: Page, act: () => Promise<void>): Promise<void> {
  const reloaded = page.waitForEvent("load", { timeout: 60_000 });
  await act();
  await reloaded;
  await expect(control(page, "settings.save")).toBeVisible({ timeout: 60_000 });
}

/** Answers whatever the browser asks. Several controls confirm before acting,
 *  and Playwright dismisses dialogs unless told otherwise — which makes those
 *  clicks silently do nothing. */
function acceptDialogs(page: Page, prompt = ""): void {
  page.on("dialog", (dialog) => void dialog.accept(prompt));
}

/** Lets the real backend answer, then edits the answer on the way through.
 *
 *  Wrapped in a `try`: a route handler can still be mid-flight when the test
 *  ends and the context closes, and a request nobody is waiting for any more is
 *  not a failure of the test that just passed. */
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

/** The heading inside a dialog, which is where a tab walk over that dialog has
 *  to start: the dialogs render at the end of the document, after every card,
 *  so a walk from the top of the page spends three hundred presses getting
 *  there. Non-focusable, so clicking it moves the starting point without
 *  focusing anything. */
const insideDialog = (page: Page, panel: ActionId) =>
  page.locator(`[data-action="${panel}"] h2`).first();

/* ────────────────────────── the shell ────────────────────────── */

test("the navbar and the log viewer", async ({ page }) => {
  // A scan reaches the portals, which the suite may not. The button is still
  // pressed for real; only what it asks for is answered from here.
  await page.route("**/api/scrapers/trigger", (route) =>
    route.fulfill({ json: { status: "started" } }));

  await page.goto("/");
  await waitForResults(page);

  // Language: the toggle names the language it will switch *to*, so the grid's
  // own words are what proves it followed.
  await press(page, "nav.language");
  await expect(page.getByText(/^\d+ immobili$/)).toBeVisible();
  await press(page, "nav.language");
  await expect(page.getByText(/^\d+ properties$/)).toBeVisible();

  await press(page, "nav.theme");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await press(page, "nav.theme");
  await expect(page.locator("html")).not.toHaveClass(/dark/);

  await press(page, "scan.now");
  await expect(control(page, "scan.now")).toBeEnabled();

  await press(page, "nav.logs");
  await expect(control(page, "logs.filter")).toBeVisible();
  await fill(page, "logs.filter", "INFO");
  await toggle(page, "logs.autoRefresh");
  await toggle(page, "logs.autoRefresh");
  // Clicking inside the viewer must not close it: that is the panel guard's
  // whole job, and without it every click on a log line dismisses the dialog.
  await press(page, "logs.panel", { position: { x: 8, y: 8 } });
  await expect(control(page, "logs.filter")).toBeVisible();
  await reachableByKeyboard(page, "the log viewer",
    ["logs.close", "logs.filter", "logs.autoRefresh"], insideDialog(page, "logs.panel"));
  await press(page, "logs.close");
  await expect(control(page, "logs.filter")).toBeHidden();

  await press(page, "nav.logs");
  await press(page, "logs.close.backdrop", { position: { x: 5, y: 5 } });
  await expect(control(page, "logs.filter")).toBeHidden();

  await press(page, "nav.settings");
  await expect(control(page, "settings.save")).toBeVisible();
  await press(page, "settings.close");
  await expect(control(page, "settings.save")).toBeHidden();

  await reachableByKeyboard(page, "the navbar", [
    "scan.now", "nav.language", "nav.theme", "nav.logs", "nav.settings",
  ]);
});

/* ────────────────────────── the filter bar ────────────────────────── */

test("every filter narrows the grid, and reset undoes all of it", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  await narrows(page,
    () => fill(page, "filters.query", "zzzzzz"),
    () => press(page, "filters.query.clear"));

  await narrows(page,
    () => fill(page, "filters.city", "Nowhere"),
    () => fill(page, "filters.city", ""));
  await narrows(page,
    () => fill(page, "filters.zone", "Nowhere"),
    () => fill(page, "filters.zone", ""));
  await narrows(page,
    () => fill(page, "filters.minPrice", "99000000"),
    () => fill(page, "filters.minPrice", ""));
  await narrows(page,
    () => fill(page, "filters.maxPrice", "1"),
    () => fill(page, "filters.maxPrice", ""));
  await narrows(page,
    () => fill(page, "filters.minSqm", "9000"),
    () => fill(page, "filters.minSqm", ""));
  await narrows(page,
    () => fill(page, "filters.maxSqm", "1"),
    () => fill(page, "filters.maxSqm", ""));
  await narrows(page,
    () => choose(page, "filters.rooms", "5"),
    () => choose(page, "filters.rooms", ""));
  await narrows(page,
    () => choose(page, "filters.floor", "top"),
    () => choose(page, "filters.floor", ""));
  await narrows(page,
    () => choose(page, "filters.status", "sold"),
    () => choose(page, "filters.status", "active"));
  await narrows(page,
    () => choose(page, "filters.source", "email"),
    () => choose(page, "filters.source", ""));
  await narrows(page,
    () => setTicked(page, "filters.priceDrops", true),
    () => setTicked(page, "filters.priceDrops", false));
  await narrows(page,
    () => setTicked(page, "filters.favorites", true),
    () => setTicked(page, "filters.favorites", false));

  // The tag and search selects only exist because the corpus has tags and
  // saved searches; their first real option is the assertion's input.
  const tag = await control(page, "filters.tag").locator("option").nth(1).getAttribute("value");
  await narrows(page,
    () => choose(page, "filters.tag", tag ?? ""),
    () => choose(page, "filters.tag", ""));
  const profile = await control(page, "filters.profile").locator("option").nth(1).getAttribute("value");
  await narrows(page,
    () => choose(page, "filters.profile", profile ?? ""),
    () => choose(page, "filters.profile", ""));

  // Sorting is the one control here that must NOT change the count: it
  // reorders. So the assertion is the order, taken from the cards themselves.
  const firstByNewest = await cards(page).first().getAttribute("aria-label");
  await choose(page, "filters.sort", "price_asc");
  await expect.poll(async () => cards(page).first().getAttribute("aria-label"))
    .not.toBe(firstByNewest);
  await choose(page, "filters.sort", "newest");

  // Buy and Rent are separate worlds, so this is a different set rather than a
  // narrower one.
  const sale = await resultCount(page);
  await press(page, "filters.contract.rent");
  await expect.poll(() => resultCount(page)).not.toBe(sale);
  await press(page, "filters.contract.sale");
  await expect.poll(() => resultCount(page)).toBe(sale);

  await reachableByKeyboard(page, "the filter bar", [
    "filters.query", "filters.contract.sale", "filters.contract.rent", "filters.city",
    "filters.zone", "filters.minPrice", "filters.maxPrice", "filters.minSqm",
    "filters.maxSqm", "filters.rooms", "filters.floor", "filters.sort", "filters.status",
    "filters.source", "filters.tag", "filters.profile", "filters.priceDrops",
    "filters.favorites", "filters.advanced.toggle", "view.grid", "view.map",
    "export.html", "export.markdown", "export.csv", "export.pdf",
    "maintenance.geocode", "maintenance.clearGeocodeCache",
  ]);

  // The advanced panel, and with it the six filters that live behind the toggle.
  await press(page, "filters.advanced.toggle");
  await expect(control(page, "filters.portal")).toBeVisible();
  await narrows(page,
    () => choose(page, "filters.portal", "idealista"),
    () => choose(page, "filters.portal", ""));
  await narrows(page,
    () => fill(page, "filters.agency", "Nowhere"),
    () => fill(page, "filters.agency", ""));
  await narrows(page,
    () => choose(page, "filters.deal", "undervalued"),
    () => choose(page, "filters.deal", ""));
  await narrows(page,
    () => fill(page, "filters.minSqmPrice", "9000000"),
    () => fill(page, "filters.minSqmPrice", ""));
  await narrows(page,
    () => fill(page, "filters.maxSqmPrice", "1"),
    () => fill(page, "filters.maxSqmPrice", ""));
  await narrows(page,
    () => setTicked(page, "filters.mergedOnly", true),
    () => setTicked(page, "filters.mergedOnly", false));
  await reachableByKeyboard(page, "the advanced filters", [
    "filters.portal", "filters.agency", "filters.deal",
    "filters.minSqmPrice", "filters.maxSqmPrice", "filters.mergedOnly",
  ]);
  await press(page, "filters.advanced.toggle");
  await expect(control(page, "filters.portal")).toBeHidden();

  // Reset is the promise that no filter is a one-way door: set several, press
  // it once, and the grid is back where it started.
  const all = await resultCount(page);
  await fill(page, "filters.city", "Milano");
  await choose(page, "filters.rooms", "3");
  await setTicked(page, "filters.favorites", true);
  await expect.poll(() => resultCount(page)).not.toBe(all);
  await press(page, "filters.reset");
  await expect.poll(() => resultCount(page)).toBe(all);
  await expect(control(page, "filters.city")).toHaveValue("");
});

test("the exports, the view switch and the maintenance actions", async ({ page, context, offlineGuard }) => {
  // A map without a tile server is the offline case rather than a special one:
  // the pins and the switch back to the grid have to work with the backdrop
  // missing, which is also what a user on a dead connection sees.
  offlineGuard.expectBlocked(/tile\.openstreetmap\.org/);

  // The dossier is generated by the backend and can be megabytes of it; what
  // this asserts is that the button hands the browser a file, which is where
  // the frontend's responsibility ends. The PDF is left alone: it is opened in
  // a tab rather than downloaded, and a popup's requests are the context's, not
  // this page's, so a page route would never see it anyway.
  await page.route("**/api/properties/export**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/plain",
      headers: { "content-disposition": 'attachment; filename="report.txt"' },
      body: "report",
    }));
  await page.route("**/api/maintenance/geocode-missing", (route) =>
    route.fulfill({ json: { scanned: 4, geocoded: 3, not_found: 1, remaining: 0, cancelled: false } }));
  await page.route("**/api/maintenance/geocode-clear-cache", (route) =>
    route.fulfill({ json: { cleared: 2 } }));

  await page.goto("/");
  await waitForResults(page);

  for (const fmt of ["export.html", "export.markdown", "export.csv"] as const) {
    const download = page.waitForEvent("download");
    await press(page, fmt);
    await (await download).cancel();
  }
  const popup = context.waitForEvent("page");
  await press(page, "export.pdf");
  await (await popup).close();

  // Map and back. The map is a real Leaflet instance with no tile server, which
  // is the offline case rather than a special one.
  await press(page, "view.map");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await press(page, "view.grid");
  await expect(cards(page).first()).toBeVisible();

  await press(page, "maintenance.geocode");
  await expect(control(page, "maintenance.result.dismiss")).toBeVisible();
  await press(page, "maintenance.result.dismiss");
  await expect(control(page, "maintenance.result.dismiss")).toBeHidden();

  await press(page, "maintenance.clearGeocodeCache");
  await expect(control(page, "maintenance.cacheCleared.dismiss")).toBeVisible();
  await press(page, "maintenance.cacheCleared.dismiss");
  await expect(control(page, "maintenance.cacheCleared.dismiss")).toBeHidden();

  // The messages that only exist when something went wrong, and the Stop that
  // only exists while the sweep runs. A sweep that never answers is what holds
  // the progress bar open long enough to press it.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.unroute("**/api/maintenance/geocode-missing");
  await page.route("**/api/maintenance/geocode-missing", async (route) => {
    await held;
    await route.fulfill({ status: 500, json: { detail: "the geocoder refused" } });
  });
  await page.route("**/api/maintenance/geocode-cancel", (route) => route.fulfill({ json: { ok: true } }));

  await press(page, "maintenance.geocode");
  await expect(control(page, "maintenance.geocode.stop")).toBeVisible();
  await press(page, "maintenance.geocode.stop");
  release();
  await expect(control(page, "toast.dismiss")).toBeVisible();
  await press(page, "toast.dismiss");
  await expect(control(page, "toast.dismiss")).toBeHidden();

  // Exporting through a refused backend: the message says what failed, and the
  // filter bar is still usable underneath it.
  await page.unroute("**/api/properties/export**");
  await page.route("**/api/properties/export**", (route) =>
    route.fulfill({ status: 500, body: "no" }));
  // With a token stored, the export stops being a navigation and becomes a
  // fetch — which is the only path that has a failure the UI can show.
  await page.evaluate(() => localStorage.setItem("apiToken", "x"));
  await page.reload();
  await waitForResults(page);
  await press(page, "export.csv");
  await expect(control(page, "toast.dismiss")).toBeVisible();
  await press(page, "toast.dismiss");
  await expect(control(page, "toast.dismiss")).toBeHidden();
  await expect(control(page, "filters.query")).toBeEnabled();
  await page.evaluate(() => localStorage.removeItem("apiToken"));
});

/* ────────────────────────── a card, and the property behind it ────────────────────────── */

test("the card's own controls", async ({ page }) => {
  acceptDialogs(page);
  await page.goto("/");
  await waitForResults(page);

  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";

  // The star, and the guard that keeps pressing it from opening the property.
  await press(card, "property.favorite");
  await expect(card.getByRole("button", { name: "Remove from favorites" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeHidden();
  await press(card, "property.favorite");

  // Tags, from the card. The picker is its own guard for the same reason: a
  // click in here must not open the property behind it.
  const chips = () => card.locator("[data-action='tags.remove']");
  await press(card, "tags.add");
  await fill(card, "tags.name", "coverage-tag");
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeHidden();
  await press(card, "tags.create");
  await expect(card.getByText("coverage-tag")).toBeVisible();
  // Removing by name rather than by position: the corpus tags about a third of
  // its properties, so the first chip on this card is not necessarily the one
  // just added.
  await card.getByRole("button", { name: /coverage-tag/i }).click();
  await expect(card.getByText("coverage-tag")).toBeHidden();

  // ...and the suggestion list, which needs a tag that already exists.
  const chipCount = await chips().count();
  await press(card, "tags.add");
  await press(card, "tags.suggest");
  await expect.poll(() => chips().count()).toBe(chipCount + 1);
  await press(card, "tags.remove");
  await expect.poll(() => chips().count()).toBe(chipCount);

  // The whole card opens the property; the title button is the keyboard route
  // to the same place. The card *is* the control here, not a container of it,
  // so it is clicked directly rather than looked for inside itself.
  await card.click({ position: { x: 8, y: 60 } });
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await press(page, "modal.close");
  await press(card, "property.open");
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await press(page, "modal.close");

  await reachableByKeyboard(page, "a card", [
    "property.open", "property.favorite", "property.hide", "tags.add",
  ]);

  // Hiding is the destructive one on the card, and the way back is the
  // Discarded filter — asserted here because a click with no undo is a trap.
  const before = await resultCount(page);
  await press(card, "property.hide");
  await expect(page.locator("article", { hasText: title })).toBeHidden();
  await choose(page, "filters.status", "hidden");
  await waitForResults(page);
  await page.locator("article", { hasText: title }).click();
  await press(page, "modal.restore");
  await choose(page, "filters.status", "active");
  await expect.poll(() => resultCount(page)).toBe(before);

  // The next page of results, which the observer would otherwise fetch on
  // scroll; the button is the fallback and a manual nudge.
  //
  // The corpus is exactly one page deep — sixty of its eighty properties are
  // for sale, and the grid's page is sixty — so against it the button would
  // never render at all. Only the FIRST page is trimmed, to half; the page the
  // button then asks for is the backend's own answer, which is the thing the
  // button has to append.
  await patched(page,
    (url) => url.pathname === "/api/properties" && !url.searchParams.get("offset"),
    (body) => ({ ...body, items: (body.items as unknown[]).slice(0, 30) }));
  await choose(page, "filters.status", "all");
  await expect.poll(() => cards(page).count()).toBe(30);
  await expect(control(page, "grid.loadMore")).toBeVisible();

  // The second page is held open for the rest of this section, and that is what
  // makes the walk below deterministic. Scrolling to the button is what puts
  // the sentinel beside it in view, so reaching it by keyboard *is* what starts
  // the fetch — with the answer released immediately the grid would complete
  // and the button would be gone before Tab arrived, and the test would be
  // measuring a race rather than the tab order.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route(
    (url) => url.pathname === "/api/properties" && url.searchParams.get("offset") === "30",
    async (route) => {
      await held;
      try {
        await route.continue();
      } catch {
        // the page went away while this was in the air
      }
    },
  );

  // Anchored on the wrapper the button sits in: it is the last thing in the
  // grid, and a walk to it from the top of the page is thirty cards of nothing.
  await reachableByKeyboard(page, "the end of the grid", ["grid.loadMore"],
    page.locator("[data-action='grid.loadMore']").locator(".."));
  // Pressed while that page is still on its way, which is the state a user
  // meets too: the button must take the press rather than have gone inert
  // under it. Both askers get the one request.
  await press(page, "grid.loadMore");
  release();
  await expect.poll(() => cards(page).count()).toBeGreaterThan(30);
});

test("the property modal, end to end", async ({ page, request, offlineGuard }) => {
  acceptDialogs(page);
  // "View on the map" ends on the map, whose tiles the harness blocks.
  offlineGuard.expectBlocked(/tile\.openstreetmap\.org/);
  // Both of these answer with the property they were asked about, because the
  // app feeds what comes back into the grid: a stub that returned nothing would
  // be testing a shape the backend never sends. The corpus itself is the source
  // of the answer; only the round trip to the portal is replaced.
  const corpus: Record<string, unknown> = {};
  for (const item of (await (await request.get("/api/properties?limit=0&status=all")).json()).items) {
    corpus[String((item as { id: number }).id)] = item;
  }
  const idFrom = (url: string) => url.match(/\/properties\/(\d+)\//)?.[1] ?? "";
  await page.route("**/api/properties/*/check", (route) =>
    route.fulfill({
      json: {
        property: corpus[idFrom(route.request().url())],
        summary: { checked: 1, gone: 0, online: 1, unknown: 0 },
      },
    }));
  await page.route("**/api/properties/*/geocode", (route) =>
    route.fulfill({ json: { property: corpus[idFrom(route.request().url())], located: true } }));

  await page.goto("/");
  await waitForResults(page);
  await cards(page).first().click();
  await expect(control(page, "modal.close")).toBeVisible();

  // Clicking inside the modal must not close it.
  await press(page, "modal.panel", { position: { x: 8, y: 8 } });
  await expect(control(page, "modal.close")).toBeVisible();

  await press(page, "modal.favorite");
  await expect(control(page, "modal.favorite")).toHaveAttribute("aria-label", "Remove from favorites");
  await press(page, "modal.favorite");

  await fill(page, "modal.notes", "seen on a Tuesday");
  await press(page, "modal.notes.save");
  await expect(control(page, "modal.notes.save")).toBeHidden();

  // The calculators are pure client-side arithmetic, so their effect is the
  // number beside them changing.
  const monthly = () => page.getByText(/Monthly payment/i).locator("..").innerText();
  const first = await monthly();
  await fill(page, "calc.mortgage.downPayment", "40");
  await expect.poll(monthly).not.toBe(first);
  const second = await monthly();
  await fill(page, "calc.mortgage.rate", "6");
  await expect.poll(monthly).not.toBe(second);
  const third = await monthly();
  await fill(page, "calc.mortgage.years", "10");
  await expect.poll(monthly).not.toBe(third);
  await fill(page, "calc.yield.rent", "1200");
  await expect(page.getByText(/Gross yield/i)).toBeVisible();
  const gross = await page.getByText(/Net yield/i).locator("..").innerText();
  await fill(page, "calc.yield.costs", "35");
  await expect.poll(() => page.getByText(/Net yield/i).locator("..").innerText()).not.toBe(gross);

  await press(page, "modal.checkOnline");
  await expect(control(page, "modal.checkOnline")).toBeEnabled();

  await reachableByKeyboard(page, "the property modal", [
    "modal.close", "modal.favorite", "modal.notes", "modal.checkOnline", "modal.viewOnMap",
    "modal.markSold", "modal.hide", "tags.add",
  ], insideDialog(page, "modal.panel"));

  // View on the map takes the modal down and puts the map up on that property.
  await press(page, "modal.viewOnMap");
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await press(page, "view.grid");
  await waitForResults(page);

  // Closing, both ways round.
  await cards(page).first().click();
  await press(page, "modal.close.backdrop", { position: { x: 5, y: 5 } });
  await expect(control(page, "modal.close")).toBeHidden();

  // Mark sold, then hide — each on its own property, each confirmed first, and
  // each proved by the property leaving the grid.
  const sold = cards(page).first();
  const soldTitle = (await sold.getAttribute("aria-label")) ?? "";
  await sold.click();
  await press(page, "modal.markSold");
  await expect(page.locator("article", { hasText: soldTitle })).toBeHidden();

  const hidden = cards(page).first();
  const hiddenTitle = (await hidden.getAttribute("aria-label")) ?? "";
  await hidden.click();
  await press(page, "modal.hide");
  await expect(page.locator("article", { hasText: hiddenTitle })).toBeHidden();
});

test("the listing reader, when one is configured", async ({ page }) => {
  // The reader asks a model at an endpoint the suite has no business reaching,
  // so the endpoint is answered from here. Everything else is the real app:
  // the setting is turned on through Settings, and the button only appears
  // because the backend saved it.
  await page.route("**/api/properties/*/audit**", (route) =>
    route.fulfill({
      json: {
        summary: "A quiet flat needing a new kitchen.",
        condition: "to_renovate", tenant: "free", costs: ["new kitchen"],
        concerns: [], negotiation: [], model: "test-model",
        created_at: new Date().toISOString(), stale: false,
      },
    }));

  await page.goto("/");
  await waitForResults(page);
  await openSettings(page);
  await setTicked(page, "settings.assistant.audit", true);
  await press(page, "settings.save");
  await expect(page.getByText("Settings saved")).toBeVisible();
  await press(page, "settings.close");

  await cards(page).first().click();
  await press(page, "modal.audit.read");
  await expect(page.getByText("A quiet flat needing a new kitchen.")).toBeVisible();
  await press(page, "modal.close");

  await openSettings(page);
  await setTicked(page, "settings.assistant.audit", false);
  await press(page, "settings.save");
  await press(page, "settings.close");
});

/* ────────────────────────── the selection bar ────────────────────────── */

test("selecting several properties, and every batch action", async ({ page }) => {
  acceptDialogs(page);
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  // The availability batch probes the portals from the backend. Held open so
  // the Stop button exists to be pressed, then answered.
  await page.route("**/api/properties/check", async (route) => {
    await held;
    await route.fulfill({
      json: { checked: 2, gone: 0, online: 2, unknown: 0, cancelled: false, aborted: false, capped: false },
    });
  });
  await page.route("**/api/properties/check/cancel", (route) => route.fulfill({ json: { ok: true } }));

  await page.goto("/");
  await waitForResults(page);

  await press(page, "selection.toggleMode");
  await expect(control(page, "selection.selectAll")).toBeVisible();

  const card = cards(page).first();
  await press(card, "property.select");
  await expect(control(page, "selection.favorite")).toBeVisible();

  // Select-all means the whole filtered set, not the loaded window.
  const total = await resultCount(page);
  await setTicked(page, "selection.selectAll", true);
  await expect(page.getByText(`Select all (${total} of ${total})`)).toBeVisible();
  await setTicked(page, "selection.selectAll", false);

  // A batch action leaves multi-select altogether when it lands (App.tsx:
  // `bulkAction` clears the selection *and* turns the mode off), so every one
  // of them starts from nothing rather than from what the last one left.
  const arm = async () => {
    if (!await control(page, "selection.selectAll").isVisible()) {
      await press(page, "selection.toggleMode");
    }
    // `aria-pressed` is the state, so a card that is already in the batch is
    // left alone rather than clicked back out of it.
    const box = control(cards(page).first(), "property.select");
    if (await box.getAttribute("aria-pressed") !== "true") await box.click();
    await expect(control(page, "selection.favorite")).toBeVisible();
  };

  await arm();
  await reachableByKeyboard(page, "the selection bar", [
    "selection.toggleMode", "selection.selectAll", "selection.favorite",
    "selection.unfavorite", "selection.hide", "selection.markSold",
    "selection.checkAvailability", "property.select",
  ]);

  // The availability batch is the one that stays in multi-select, because it
  // reports rather than changes.
  await press(page, "selection.checkAvailability");
  await expect(control(page, "selection.stopCheck")).toBeVisible();
  await press(page, "selection.stopCheck");
  release();
  await expect(control(page, "selection.dismissSummary")).toBeVisible();
  await press(page, "selection.dismissSummary");
  await expect(control(page, "selection.dismissSummary")).toBeHidden();

  await arm();
  await press(page, "selection.favorite");
  await expect(cards(page).first().getByRole("button", { name: "Remove from favorites" }))
    .toBeVisible();
  await arm();
  await press(page, "selection.unfavorite");
  await expect(cards(page).first().getByRole("button", { name: "Add to favorites" }))
    .toBeVisible();

  // The two that change the grid. Each takes its property out of it.
  await arm();
  const soldTitle = (await cards(page).first().getAttribute("aria-label")) ?? "";
  await press(page, "selection.markSold");
  await expect(page.locator("article", { hasText: soldTitle })).toBeHidden();

  await arm();
  const hiddenTitle = (await cards(page).first().getAttribute("aria-label")) ?? "";
  await press(page, "selection.hide");
  await expect(page.locator("article", { hasText: hiddenTitle })).toBeHidden();

  // Leaving multi-select by hand clears what was selected, so the next entry
  // starts empty.
  await arm();
  await press(page, "selection.toggleMode");
  await expect(control(page, "selection.selectAll")).toBeHidden();
});

/* ────────────────────────── the map ────────────────────────── */

test("drawing an area on the map", async ({ page, offlineGuard }) => {
  offlineGuard.expectBlocked(/tile\.openstreetmap\.org/);
  await page.route("**/api/maintenance/geocode-missing", (route) =>
    route.fulfill({ json: { scanned: 2, geocoded: 2, not_found: 0, remaining: 0, cancelled: false } }));

  await page.goto("/");
  await waitForResults(page);
  await press(page, "view.map");
  const map = page.locator(".leaflet-container");
  await expect(map).toBeVisible();

  // Arming and disarming, on both tools. Being armed is what puts the Clear
  // control on screen, so that is the state rather than a class on the button.
  await press(page, "map.drawRadius");
  await expect(control(page, "map.clearZone")).toBeVisible();
  await press(page, "map.drawRadius");
  await expect(control(page, "map.clearZone")).toBeHidden();
  await press(page, "map.drawArea");
  await expect(control(page, "map.drawArea")).toHaveText(/Finish/i);

  // Three corners make a polygon, which becomes a filter on the grid.
  const box = (await map.boundingBox())!;
  for (const [dx, dy] of [[0.3, 0.3], [0.7, 0.3], [0.5, 0.7]] as const) {
    await page.mouse.click(box.x + box.width * dx, box.y + box.height * dy);
  }
  await press(page, "map.drawArea");
  await expect(control(page, "map.clearZone")).toBeVisible();
  await press(page, "map.clearZone");
  await expect(control(page, "map.clearZone")).toBeHidden();

  await reachableByKeyboard(page, "the map", ["map.drawRadius", "map.drawArea", "view.grid"]);
});

/* ────────────────────────── the insight panels ────────────────────────── */

test("the three insight panels", async ({ page }) => {
  // The trend chart needs a history the demo corpus deliberately does not
  // invent: a snapshot is one row per day, and seeding fake ones would make the
  // corpus claim a past it never had. The three responses are answered here so
  // the controls that only exist with a history can be driven.
  const day = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);
  await page.route("**/api/pricing-trends/areas**", (route) =>
    route.fulfill({ json: [
      { city: "Milano", zone: "Navigli", point_count: 9 },
      { city: "Milano", zone: "Isola", point_count: 7 },
    ] }));
  // By pathname, not by glob: `?` is a single-character wildcard in a URL
  // pattern, so `pricing-trends?**` would also swallow the areas route above.
  await page.route((url) => url.pathname === "/api/pricing-trends", (route) =>
    route.fulfill({ json: {
      city: "Milano", zone: "Navigli",
      points: [
        { captured_on: day(9), median_sqm_price: 5100, listing_count: 12 },
        { captured_on: day(4), median_sqm_price: 5300, listing_count: 14 },
        { captured_on: day(1), median_sqm_price: 5450, listing_count: 15 },
      ],
    } }));

  await page.goto("/");
  await waitForResults(page);

  await press(page, "health.toggle");
  await press(page, "health.toggle");
  await press(page, "velocity.toggle");
  await press(page, "velocity.toggle");

  await press(page, "trends.toggle");
  await expect(control(page, "trends.area")).toBeVisible();
  await choose(page, "trends.area", "Milano|Isola");
  await choose(page, "trends.area", "Milano|Navigli");

  await press(page, "trends.comparables");
  await expect(control(page, "trends.openProperty")).toBeVisible();
  await reachableByKeyboard(page, "the trends panel", [
    "trends.toggle", "trends.area", "trends.comparables", "trends.openProperty",
  ]);
  await press(page, "trends.openProperty");
  await expect(control(page, "modal.close")).toBeVisible();
  await press(page, "modal.close");
  await press(page, "trends.comparables");
  await expect(control(page, "trends.openProperty")).toBeHidden();
  await press(page, "trends.toggle");
});

/* ────────────────────────── monitored searches ────────────────────────── */

/* Before the specs that create searches, so it works on the corpus's own three
   rather than on whatever they left behind. Merging is the exception and lives
   with them: see the comment where it is. */
test("the list of searches, one row and in bulk", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  const rows = page.locator("[data-action='profiles.row.select']");
  await expect(rows.first()).toBeVisible();

  // One row: pause it, put its alerts somewhere else, and open it for editing.
  await toggle(page, "profiles.row.active");
  await toggle(page, "profiles.row.active");
  // A named channel rather than a position: the first option is "wherever the
  // account sends things", whose value is the empty string, and on the bulk
  // select that is also the disabled placeholder's value.
  await choose(page, "profiles.row.notify", "telegram");
  await press(page, "profiles.row.edit");
  await expect(
    control(page, "profiles.url.url").or(control(page, "profiles.builder.city")),
  ).toBeVisible();

  await reachableByKeyboard(page, "a saved search", [
    "profiles.row.select", "profiles.row.notify", "profiles.row.active",
    "profiles.row.edit", "profiles.row.delete",
  ]);

  // In bulk: select everything, act on it, and clear.
  await setTicked(page, "profiles.bulk.selectAll", true);
  await expect(control(page, "profiles.bulk.pause")).toBeVisible();
  await press(page, "profiles.bulk.pause");
  await expect(control(page, "profiles.row.active")).not.toBeChecked();
  await press(page, "profiles.bulk.activate");
  await expect(control(page, "profiles.row.active")).toBeChecked();
  // Not `choose`: this select is deliberately not a state. It stays on its
  // placeholder because the selection can hold searches with different
  // channels, so the effect to assert is on the rows it changed.
  await control(page, "profiles.bulk.notify").selectOption("telegram");
  await expect(control(page, "profiles.row.notify")).toHaveValue("telegram");

  // Deleting in bulk opens the same dialog one row does, and backing out of it
  // must leave every search where it was.
  const before = await page.locator("[data-action='profiles.row.delete']").count();
  await press(page, "profiles.bulk.delete");
  await expect(control(page, "profiles.delete.cancel")).toBeVisible();
  await press(page, "profiles.delete.cancel");
  await expect(page.locator("[data-action='profiles.row.delete']")).toHaveCount(before);

  await press(page, "profiles.bulk.clear");
  await expect(control(page, "profiles.bulk.pause")).toBeHidden();
});

test("creating a search, three ways", async ({ page }) => {
  // Merging asks for the name the two searches will share, and separating asks
  // for confirmation. Dismissed — which is what Playwright does unless told
  // otherwise — both return without doing anything at all.
  acceptDialogs(page, "Coverage merged search");
  await page.goto("/");
  await waitForResults(page);

  // Mode switching is mutually exclusive, and each button closes its own panel.
  await press(page, "profiles.mode.url");
  await expect(control(page, "profiles.url.url")).toBeVisible();
  await press(page, "profiles.mode.builder");
  await expect(control(page, "profiles.builder.city")).toBeVisible();
  await press(page, "profiles.mode.assistant");
  await expect(control(page, "profiles.assistant.query")).toBeVisible();

  // The plain-language box: an example fills it, and Enter is the same as the
  // button. This query has no alternatives, so it lands in the builder.
  await press(page, "profiles.assistant.example");
  await expect(control(page, "profiles.assistant.query")).not.toHaveValue("");
  await fill(page, "profiles.assistant.query", "bilocale a Milano fino a 300000 euro");
  await press(page, "profiles.assistant.ask");
  await expect(control(page, "profiles.builder.city")).toBeVisible();
  await expect(control(page, "profiles.builder.city")).toHaveValue(/Milano/i);

  // Generate is deliberately left out here: it is disabled until a city is
  // filled, and a disabled control is not in the tab order — correctly. It gets
  // its own walk below, once the form is complete.
  await reachableByKeyboard(page, "the builder", [
    "profiles.builder.contract", "profiles.builder.city", "profiles.builder.province",
    "profiles.builder.zone", "profiles.builder.minPrice", "profiles.builder.maxPrice",
    "profiles.builder.minRooms", "profiles.builder.minSqm", "profiles.builder.floor",
    "profiles.builder.condition", "profiles.builder.feature", "profiles.builder.name",
    "profiles.builder.keywords", "profiles.builder.reword",
  ]);

  // Back to the plain box and out again through the two escape hatches to the
  // URL form, each of which is a link the builder offers where a filter is
  // missing.
  await press(page, "profiles.builder.reword");
  await expect(control(page, "profiles.assistant.query")).toBeVisible();
  await press(page, "profiles.mode.builder");
  await press(page, "profiles.builder.toUrlIntro");
  await expect(control(page, "profiles.url.url")).toBeVisible();
  await press(page, "profiles.mode.builder");
  await press(page, "profiles.builder.toUrlTip");
  await expect(control(page, "profiles.url.url")).toBeVisible();

  // Every field of the guided form, then the URLs it builds.
  await press(page, "profiles.mode.builder");
  await choose(page, "profiles.builder.contract", "rent");
  await choose(page, "profiles.builder.contract", "sale");
  await fill(page, "profiles.builder.city", "Milano");
  await fill(page, "profiles.builder.province", "MI");
  await fill(page, "profiles.builder.zone", "Isola");
  await fill(page, "profiles.builder.minPrice", "150000");
  await fill(page, "profiles.builder.maxPrice", "400000");
  await choose(page, "profiles.builder.minRooms", "2");
  await fill(page, "profiles.builder.minSqm", "60");
  await choose(page, "profiles.builder.floor", "top");
  await choose(page, "profiles.builder.condition", "good");
  await toggle(page, "profiles.builder.feature");
  await fill(page, "profiles.builder.name", "Coverage builder search");
  await fill(page, "profiles.builder.keywords", "asta");

  await reachableByKeyboard(page, "the filled builder", ["profiles.builder.generate"]);
  await press(page, "profiles.builder.generate");
  await expect(control(page, "profiles.builder.create")).toBeVisible();
  await toggle(page, "profiles.builder.usePortal");
  await toggle(page, "profiles.builder.usePortal");
  await press(page, "profiles.builder.create");
  await expect(page.getByText("Coverage builder search").first()).toBeVisible();

  // The URL form, which is the most powerful path and says so.
  await press(page, "profiles.mode.url");
  await fill(page, "profiles.url.name", "Coverage URL search");
  await fill(page, "profiles.url.keywords", "asta");
  await fill(page, "profiles.url.url",
    "https://www.immobiliare.it/vendita-case/milano/?criterio=rilevanza&prezzoMassimo=500000");
  await press(page, "profiles.url.extract");
  await expect(control(page, "profiles.builder.city")).toHaveValue(/Milano/i);
  await press(page, "profiles.mode.url");
  await fill(page, "profiles.url.name", "Coverage URL search");
  await fill(page, "profiles.url.url",
    "https://www.immobiliare.it/vendita-case/milano/?criterio=rilevanza&prezzoMassimo=500000");
  await reachableByKeyboard(page, "the URL form", [
    "profiles.url.name", "profiles.url.keywords", "profiles.url.url",
    "profiles.url.extract", "profiles.url.save",
  ]);
  await press(page, "profiles.url.save");
  await expect(page.getByText("Coverage URL search").first()).toBeVisible();

  // Merging two searches into one row, and splitting them again. It belongs
  // here rather than with the rest of the list because it needs searches whose
  // URL the backend will take back: renaming goes through the same full-profile
  // PUT as editing, and the demo corpus's searches point at `demo.invalid`,
  // which `SearchProfileIn` refuses by design. The two just created carry real
  // portal URLs, so they are the pair this can be proved on.
  const row = (name: string) =>
    page.locator("li", { hasText: name }).locator("[data-action='profiles.row.select']").first();
  const listed = page.locator("[data-action='profiles.row.delete']");
  const rowsBefore = await listed.count();
  await row("Coverage builder search").check();
  await row("Coverage URL search").check();
  await press(page, "profiles.bulk.merge");
  await expect(listed).toHaveCount(rowsBefore - 1);
  await expect(control(page, "profiles.row.separate")).toBeVisible();
  await press(page, "profiles.row.separate");
  await expect(listed).toHaveCount(rowsBefore);
});

test("one query, several searches", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // A query with an alternative in it is answered as a list to review before
  // anything is created — dropping one here is cheaper than deleting a profile.
  await press(page, "profiles.mode.assistant");
  await fill(page, "profiles.assistant.query",
    "bilocale a Milano o trilocale a Torino");
  await press(page, "profiles.assistant.ask");
  await expect(control(page, "profiles.multi.create")).toBeVisible();

  await press(page, "profiles.multi.edit");
  await expect(control(page, "profiles.builder.city")).toBeVisible();
  await press(page, "profiles.mode.assistant");
  await fill(page, "profiles.assistant.query", "bilocale a Milano o trilocale a Torino");
  await press(page, "profiles.assistant.ask");

  await press(page, "profiles.multi.reword");
  await expect(control(page, "profiles.assistant.query")).toBeVisible();
  await press(page, "profiles.assistant.ask");
  await expect(control(page, "profiles.multi.create")).toBeVisible();

  await fill(page, "profiles.multi.keywords", "asta");
  await toggle(page, "profiles.multi.usePortal");
  await toggle(page, "profiles.multi.usePortal");
  await reachableByKeyboard(page, "the alternatives", [
    "profiles.multi.reword", "profiles.multi.edit", "profiles.multi.drop",
    "profiles.multi.usePortal", "profiles.multi.keywords", "profiles.multi.create",
  ]);

  const alternatives = await page.locator("[data-action='profiles.multi.drop']").count();
  await press(page, "profiles.multi.drop");
  await expect.poll(() => page.locator("[data-action='profiles.multi.drop']").count())
    .toBe(alternatives - 1);
  await press(page, "profiles.multi.create");
  await expect(control(page, "profiles.multi.create")).toBeHidden();
});

test("deleting a search, and the counts it shows first", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // The dialog shows what would go and what is spared, which is why it is a
  // dialog and not a confirm().
  await press(page, "profiles.row.delete");
  await expect(control(page, "profiles.delete.cancel")).toBeVisible();
  await press(page, "profiles.delete.panel", { position: { x: 8, y: 8 } });
  await expect(control(page, "profiles.delete.cancel")).toBeVisible();
  await reachableByKeyboard(page, "the delete dialog", [
    "profiles.delete.cancel", "profiles.delete.keepResults",
  ], insideDialog(page, "profiles.delete.panel"));
  await press(page, "profiles.delete.cancel");
  await expect(control(page, "profiles.delete.cancel")).toBeHidden();

  await press(page, "profiles.row.delete");
  await press(page, "profiles.delete.backdrop", { position: { x: 5, y: 5 } });
  await expect(control(page, "profiles.delete.cancel")).toBeHidden();

  // Keep the results: the search goes, the properties stay.
  const searches = await page.locator("[data-action='profiles.row.delete']").count();
  const properties = await resultCount(page);
  await press(page, "profiles.row.delete");
  await press(page, "profiles.delete.keepResults");
  await expect.poll(() => page.locator("[data-action='profiles.row.delete']").count())
    .toBe(searches - 1);
  await expect.poll(() => resultCount(page)).toBe(properties);

  // With the results: only the ones nothing else covers go with it.
  await press(page, "profiles.row.delete");
  await expect(control(page, "profiles.delete.withResults")).toBeVisible();
  await press(page, "profiles.delete.withResults");
  await expect(control(page, "profiles.delete.withResults")).toBeHidden();
});

/* ────────────────────────── settings ────────────────────────── */

test("every setting, and the tests beside them", async ({ page }) => {
  // Telegram and SMTP send from the backend; the harvester subtree only renders
  // when Playwright is importable, which it deliberately is not here. The
  // controls are pressed for real against answers from this side.
  // Both directions, not just the read: a save answers with the settings too,
  // and an unpatched answer to the PUT takes the harvester subtree back off
  // the screen the moment anything is saved.
  await patched(page, (url) => url.pathname === "/api/settings",
    (body) => ({ ...body, datadome_harvester_available: true, camoufox_available: false }));
  await page.route("**/api/settings/telegram-test", (route) =>
    route.fulfill({ json: { ok: true } }));
  await page.route("**/api/settings/email-test", (route) =>
    route.fulfill({ json: { ok: true } }));
  await page.route("**/api/settings/install-camoufox", (route) =>
    route.fulfill({ json: { ok: true, message: "installed" } }));
  await page.route("**/api/maintenance/commutes", (route) =>
    route.fulfill({ json: { scanned: 0, routed: 0, remaining: 0 } }));

  await page.goto("/");
  await waitForResults(page);
  await openSettings(page);

  // Telegram
  await fill(page, "settings.telegram.token", "1234:coverage");
  await fill(page, "settings.telegram.chatId", "424242");
  await toggle(page, "settings.telegram.actions");
  await toggle(page, "settings.telegram.actions");
  await toggle(page, "settings.telegram.enable");
  await press(page, "settings.telegram.test");
  await expect(control(page, "settings.telegram.test")).toBeEnabled();
  await toggle(page, "settings.telegram.enable");

  // Email
  await fill(page, "settings.email.host", "smtp.example.test");
  await fill(page, "settings.email.port", "2525");
  await fill(page, "settings.email.user", "someone");
  await fill(page, "settings.email.password", "hunter2");
  await fill(page, "settings.email.from", "from@example.test");
  await fill(page, "settings.email.to", "to@example.test");
  await toggle(page, "settings.email.enable");
  await press(page, "settings.email.test");
  await expect(control(page, "settings.email.test")).toBeEnabled();
  await toggle(page, "settings.email.enable");

  // Scanning
  await choose(page, "settings.scanning.interval", "120");
  await toggle(page, "settings.scanning.pause");
  await toggle(page, "settings.scanning.pause");
  await choose(page, "settings.scanning.healthAfter", "5");
  await fill(page, "settings.scanning.keywords", "asta, nuda proprieta");

  // Smart match: the checkbox is what reveals the rest of the section.
  await setTicked(page, "settings.match.enable", true);
  await expect(control(page, "settings.match.maxPrice")).toBeVisible();
  await fill(page, "settings.match.maxPrice", "450000");
  await fill(page, "settings.match.minRooms", "3");
  await fill(page, "settings.match.minSqm", "80");
  await fill(page, "settings.match.minFloor", "2");
  await fill(page, "settings.match.features", "balcone, ascensore");
  await fill(page, "settings.match.zones", "Isola, Navigli");
  await setTicked(page, "settings.match.enable", false);
  await expect(control(page, "settings.match.maxPrice")).toBeHidden();

  // Commute: same shape, plus a list that grows and shrinks.
  await setTicked(page, "settings.commute.enable", true);
  await fill(page, "settings.commute.osrmUrl", "http://127.0.0.1:5000");
  await press(page, "settings.commute.addPoint");
  await fill(page, "settings.commute.pointName", "Work");
  await fill(page, "settings.commute.pointAddress", "Piazza Duomo, Milano");
  await choose(page, "settings.commute.pointMode", "foot");
  await press(page, "settings.commute.compute");
  await expect(control(page, "settings.commute.compute")).toBeEnabled();
  await press(page, "settings.commute.removePoint");
  await expect(control(page, "settings.commute.pointName")).toBeHidden();
  await setTicked(page, "settings.commute.enable", false);

  // The assistant and the listing reader share one endpoint, so either turns
  // the connection fields on.
  await choose(page, "settings.assistant.backend", "llm");
  await expect(control(page, "settings.assistant.baseUrl")).toBeVisible();
  await fill(page, "settings.assistant.baseUrl", "http://127.0.0.1:11434/v1");
  await fill(page, "settings.assistant.model", "llama3.1");
  await fill(page, "settings.assistant.apiKey", "sk-coverage");
  await toggle(page, "settings.assistant.audit");
  await toggle(page, "settings.assistant.audit");
  await choose(page, "settings.assistant.backend", "deterministic");

  // Staying unblocked.
  await fill(page, "settings.scraping.proxyUrl", "http://127.0.0.1:8888");
  await fill(page, "settings.scraping.proxyPool", "http://127.0.0.1:8888\nhttp://127.0.0.1:8889");
  await fill(page, "settings.scraping.idealistaKey", "id-key");
  await fill(page, "settings.scraping.idealistaSecret", "id-secret");
  await fill(page, "settings.scraping.idealistaMaxPages", "3");
  await choose(page, "settings.scraping.apiProvider", "zyte");
  await fill(page, "settings.scraping.apiKey", "scrape-key");
  await choose(page, "settings.scraping.apiMode", "always");
  await fill(page, "settings.scraping.cookie", "datadome=coverage");
  await toggle(page, "settings.scraping.autoRefresh");
  await toggle(page, "settings.scraping.autoRefresh");
  await toggle(page, "settings.scraping.browserFirst");
  await toggle(page, "settings.scraping.browserFirst");
  await toggle(page, "settings.scraping.browserHeadful");
  await toggle(page, "settings.scraping.browserHeadful");
  await toggle(page, "settings.scraping.humanize");
  await toggle(page, "settings.scraping.humanize");
  await choose(page, "settings.scraping.engine", "chromium");
  await choose(page, "settings.scraping.engine", "auto");
  await press(page, "settings.scraping.installCamoufox");
  await expect(control(page, "settings.scraping.installCamoufox")).toBeEnabled();

  // The harvest, and the Stop that only exists while it runs. Matched on the
  // pathname: the refresh carries `?portal=`, which a glob would not match, and
  // the cancel is one segment deeper.
  let release: () => void = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route((url) => url.pathname === "/api/settings/datadome-refresh", async (route) => {
    await held;
    await route.fulfill({
      json: { ok: true, portal: "immobiliare", updated_at: new Date().toISOString(), cookie_preview: "…" },
    });
  });
  await page.route((url) => url.pathname === "/api/settings/datadome-refresh/cancel", (route) =>
    route.fulfill({ json: { ok: true } }));
  await press(page, "settings.scraping.grabCookie");
  await expect(control(page, "settings.scraping.stopGrab")).toBeVisible();
  await press(page, "settings.scraping.stopGrab");
  release();
  await expect(control(page, "settings.scraping.grabCookie")).toBeEnabled();

  // The system section, minus the four that would end the run — those are the
  // last test in this file, once nothing else needs the corpus.
  await fill(page, "settings.system.apiToken", "");

  await reachableByKeyboard(page, "settings", [
    "settings.close", "settings.telegram.token", "settings.telegram.chatId",
    "settings.email.host", "settings.scanning.interval", "settings.scanning.keywords",
    "settings.scraping.proxyUrl", "settings.system.apiToken", "settings.system.restart",
    "settings.system.backupNow", "settings.system.backupImport",
    "settings.footer.close", "settings.save",
  ], insideDialog(page, "settings.panel"));

  await press(page, "settings.save");
  await expect(page.getByText("Settings saved")).toBeVisible();

  // Clicking inside the dialog must not close it; the three ways out must.
  await press(page, "settings.panel", { position: { x: 8, y: 8 } });
  await expect(control(page, "settings.save")).toBeVisible();
  await press(page, "settings.footer.close");
  await expect(control(page, "settings.save")).toBeHidden();
  await openSettings(page);
  await press(page, "settings.close.backdrop", { position: { x: 5, y: 5 } });
  await expect(control(page, "settings.save")).toBeHidden();
});

/* ────────────────────────── when the backend refuses ────────────────────────── */

test("the app stays usable when the backend refuses everything", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await press(page, "filters.advanced.toggle");
  await press(page, "selection.toggleMode");
  await press(page, "property.select");

  // From here on nothing the app asks for is answered. The bar is low and it
  // is the right one: whatever a control does, the user must be left with a
  // page they can still operate rather than a blank screen or a stuck spinner.
  await page.route("**/api/**", (route) =>
    route.fulfill({ status: 500, json: { detail: "refused, on purpose" } }));

  const skip: ActionId[] = [
    // Each of these takes the page away from under the sweep, or hands it to
    // the browser rather than to the app.
    "nav.language", "nav.theme", "view.map",
    "export.pdf", "export.html", "export.markdown", "export.csv",
    // ...each of these puts an overlay over everything the sweep has left to
    // press, which would turn the rest of it into two hundred timeouts,
    "nav.settings", "nav.logs", "property.card", "property.open",
    "profiles.row.delete", "profiles.bulk.delete", "trends.openProperty",
    // ...and each of these asks a question the sweep is not there to answer.
    "property.hide", "selection.hide", "selection.markSold",
  ];
  for (const id of await visibleActions(page, skip)) {
    await page.locator(`[data-action="${id}"]`).first().click({ timeout: 5_000 }).catch(() => {});
    await expect(
      page.getByRole("heading", { name: "Real Estate Search" }),
      `${id} took the app down when the backend refused it`,
    ).toBeVisible();
    await expect(page.locator("body")).not.toBeEmpty();
  }

  // The sweep left a message behind for every refusal it collected. Clear them
  // so what follows is about the one write it is actually testing.
  const messages = page.locator('[data-action="toast.dismiss"]');
  while (await messages.count()) await messages.first().click();

  // A failed write says so, and the message can be dismissed without a reload.
  await press(page, "property.favorite");
  await expect(control(page, "toast.dismiss")).toBeVisible();
  await press(page, "toast.dismiss");
  await expect(control(page, "toast.dismiss")).toBeHidden();

  // Settings that cannot load must still be closable — the dialog used to open
  // on nothing at all, with not even a way out of it.
  await press(page, "nav.settings");
  await expect(control(page, "settings.loadError.retry")).toBeVisible();
  await press(page, "settings.loadError.retry");
  await expect(control(page, "settings.loadError.retry")).toBeVisible();
  await press(page, "settings.loadError.close");
  await expect(control(page, "settings.loadError.close")).toBeHidden();
});

test("a refused write says what to do, and the retry does it", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // Refused once and only once. That is what makes the retry a real assertion:
  // the second attempt goes through, so a button that merely looked like a
  // retry — or one that re-sent nothing — would leave the star unchanged.
  let refuse = true;
  await page.route("**/api/properties/*", async (route) => {
    // The star is a PATCH on the property; everything else through this pattern
    // is the grid re-reading itself and has to be let through.
    if (!refuse || route.request().method() !== "PATCH") return route.fallback();
    refuse = false;
    await route.fulfill({ status: 500, json: { detail: "the database is locked" } });
  });

  // Scoped to one card rather than to the page: the grid re-reads itself after
  // the write, and the assertion has to be about the property that was starred.
  // Its state is in the label rather than in the glyph: the star is a drawing,
  // and a drawing has no text to compare.
  const star = control(cards(page).first(), "property.favorite");
  const before = (await star.getAttribute("aria-label")) ?? "";
  await star.click();

  // What happened, what to do about it, and the one-click way to do it.
  const message = page.getByRole("alert").first();
  await expect(message).toContainText(/database is locked/i);
  await expect(message).toContainText(/backend|riprova|try again/i);
  await expect(control(page, "toast.action")).toBeVisible();

  await press(page, "toast.action");
  // The message goes with the press, and the write it was about lands.
  await expect(control(page, "toast.action")).toBeHidden();
  await expect(star).not.toHaveAttribute("aria-label", before);
});

test("the token prompt, when the backend asks for one", async ({ page }) => {
  // Optional API auth is off by default (invariant 14: the bind address is the
  // control), so the only honest way to reach this screen is a 401.
  await page.route("**/api/settings", (route) =>
    route.fulfill({ status: 401, json: { detail: "token required" } }));

  // Nothing needs pressing: the dashboard asks for its settings on load, so the
  // prompt is what a user meets rather than something a control opens.
  await page.goto("/");
  await expect(control(page, "auth.token")).toBeVisible();

  await fill(page, "auth.token", "not-the-token");
  await reachableByKeyboard(page, "the token prompt", ["auth.token"],
    insideDialog(page, "auth.submit"));
  // Enter inside the form is the submit: the form is the control, not the button.
  await control(page, "auth.token").press("Enter");
  await expect(page.getByText(/not accepted|non . stato accettato/i)).toBeVisible();
});

test("the last-resort screen after a rendering error", async ({ page }) => {
  // A card with no listings array is a shape the frontend has no branch for, so
  // rendering it throws — which is the only way to reach the boundary, and the
  // reason the boundary exists. Manufacturing it here beats shipping a
  // component that crashes on purpose.
  const grid = (url: URL) => url.pathname === "/api/properties";
  await page.route(grid, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.items = [{ ...body.items[0], listings: null }];
    return route.fulfill({ json: body });
  });

  await page.goto("/");
  await expect(control(page, "app.crash.reload")).toBeVisible();
  await page.unroute(grid);
  await press(page, "app.crash.reload");
  await waitForResults(page);
});

/* ────────────────────────── the destructive ones, last ────────────────────────── */

test("the backups and the resets", async ({ page }) => {
  // Last on purpose: these empty the database the rest of the suite reads, so
  // they run once nothing else needs it. The run seeds a fresh data directory
  // every time (playwright.config.ts), so nothing here outlives the run.
  acceptDialogs(page, "RESTORE");
  await page.route("**/api/system/restart", (route) =>
    route.fulfill({ json: { ok: true, reload: false } }));
  await page.route("**/api/settings/install-harvester", (route) =>
    route.fulfill({ json: { ok: true, message: "installed" } }));

  await page.goto("/");
  await waitForResults(page);
  await openSettings(page);

  await press(page, "settings.scraping.installHarvester");
  await expect(control(page, "settings.scraping.installHarvester")).toBeEnabled();

  // Restarting asks, waits for the process to answer again and then reloads the
  // page — so the page coming back is the signal, not the button re-enabling.
  // It comes back *into Settings*: the dialog is an address now, and a reload
  // lands where it left. Reopening it would only find its own backdrop.
  await throughAReload(page, () => press(page, "settings.system.restart"));
  await waitForResults(page);

  // A snapshot, then the two things that can be done with one.
  await press(page, "settings.system.backupNow");
  await expect(control(page, "settings.system.backupDownload")).toBeVisible();
  const download = page.waitForEvent("download");
  await press(page, "settings.system.backupDownload");
  const file = await (await download).path();

  // Bringing one in: the picker is what the button opens, the hidden input is
  // what does the work, and the file is one this app just produced.
  page.on("filechooser", (chooser) => void chooser.setFiles(file!));
  await press(page, "settings.system.backupImport");
  await expect(page.getByText(/Added as|Aggiunt/i)).toBeVisible();

  // Restoring says so, and reloads the page a moment later onto the database it
  // has just put back. Both halves are asserted: the message is what the user
  // is told, the reload is what actually happened.
  await throughAReload(page, async () => {
    await press(page, "settings.system.backupRestore");
    await expect(page.getByText(/Restored|Ripristinat/i)).toBeVisible();
  });

  // The three resets, smallest first. Each reloads the page when it lands, and
  // the page comes back into Settings on its own — so the reload is waited for
  // and the dialog is never reopened.
  for (const reset of ["settings.system.resetTrends", "settings.system.resetDashboard",
    "settings.system.resetFactory"] as const) {
    await throughAReload(page, () => press(page, reset));
  }
});

/* ────────────────────────── the two gates ────────────────────────── */

test("no handler ships without an inventoried identity", () => {
  const elements = interactiveElements(SRC);
  const where = (e: { file: string; line: number; tag: string }) =>
    `${e.file}:${e.line} <${e.tag}>`;

  expect(
    elements.filter((e) => !e.action && !e.dynamic).map(where),
    "these elements carry a handler and no data-action. Give each one an id and "
    + "a row in e2e/actions.ts: a control with no identity is one no test can "
    + "name, and one nobody will notice went untested.",
  ).toEqual([]);

  expect(
    elements.filter((e) => e.action && !(e.action in INVENTORY)).map(where),
    "these elements name an action the inventory does not carry. Add the row, or "
    + "correct the id.",
  ).toEqual([]);

  // The other direction. A dynamic `data-action={...}` is only honest if the
  // value it can take is written down as a literal somewhere in `src/`.
  const literals = literalsInSource(SRC);
  expect(
    ACTION_IDS.filter((id) => !literals.has(id)),
    "these inventory rows name a control that is no longer in the source. An "
    + "inventory that outlives what it describes is a list nobody trusts: delete "
    + "the row with the control.",
  ).toEqual([]);

  // Reported rather than asserted on an exact number: the count is the size of
  // the app's surface, and pinning it would fail on every button ever added.
  console.log(
    `[A.5] ${elements.length} interactive elements, ${ACTION_IDS.length} inventoried actions.`,
  );
  expect(elements.length).toBeGreaterThan(200);
});

test("no inventoried action ships untested", () => {
  const fired = readRecordings();
  const blocked = ACTION_IDS.filter((id) => INVENTORY[id].blocked);
  const untested = ACTION_IDS.filter((id) => !fired.has(id) && !INVENTORY[id].blocked);

  expect(
    untested,
    "the whole run never fired these. Either a spec has to exercise them — the "
    + "point of the inventory is that no control ships untried — or, if the suite "
    + "genuinely cannot, the row needs a `blocked` reason saying so in words "
    + "somebody can argue with.",
  ).toEqual([]);

  // A `blocked` row is a hole in the promise, so the holes are counted out loud
  // rather than left for a reader to total up.
  console.log(
    `[A.5] ${fired.size} of ${ACTION_IDS.length} actions exercised; `
    + `${blocked.length} declared unreachable: ${blocked.join(", ") || "none"}.`,
  );
  expect(
    blocked.filter((id) => (INVENTORY[id].blocked ?? "").length < 40),
    "a blocked row costs a real reason, not a word.",
  ).toEqual([]);
  expect(blocked.length).toBeLessThanOrEqual(3);

  // And nothing fired that the inventory does not know about — the runtime half
  // of the check the static pass cannot make on a dynamic `data-action`.
  expect(
    [...fired].filter((id) => !(id in INVENTORY)),
    "the page fired an action the inventory does not carry.",
  ).toEqual([]);
});
