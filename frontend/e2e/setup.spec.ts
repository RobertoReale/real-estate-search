/** The capability setup: skipping the whole of it, and answering one thing per
 *  step and finding it still there afterwards.
 *
 *  Against the empty backend (see harness/empty.ts) for two reasons. The first
 *  is the same as the guided run's: this is the state a fresh install is in, and
 *  the seeded corpus cannot be put back into it. The second is that these tests
 *  *write settings*, and the settings they write — a mail server, an API key —
 *  would be the seeded database's settings for every journey that ran after
 *  them.
 *
 *  Controls are addressed by their label here and not by `data-action`, which is
 *  the opposite of every other spec. It is deliberate and it is the wizard's own
 *  design: five screens draw the same six controls with different settings
 *  behind them, so the inventory has one row per control rather than one per
 *  field (`actions.ts`, `SetupRoute.tsx`) and the label is what tells two text
 *  boxes on one step apart. The coverage gate is unaffected — the recorder
 *  credits the `data-action` on whatever was actually operated, however the test
 *  found it.
 *
 *  Nothing here fills in a Telegram token, and that is not an oversight: the
 *  backend starts its button poller unconditionally, so a token plus the switch
 *  in a test database is a standing connection to api.telegram.org from a suite
 *  that is not allowed to leave the machine. Being told is answered by email,
 *  which reaches a mail server only when there is something to send.
 */
import type { Locator, Page } from "@playwright/test";

import { checkScreen, expect, test } from "./fixtures";
import { cards } from "./harness/dashboard";
import { control, fill, press } from "./harness/drive";
import { useEmptyBackend } from "./harness/empty";

const path = (page: Page) => new URL(page.url()).pathname;

/** The control this step labels with these exact words. Exact, because "Pages
 *  per search" is a prefix of "Pages per search on the Idealista API" and a
 *  substring match would silently answer the wrong question. */
function labelled(page: Page, label: string): Locator {
  return page.getByLabel(label, { exact: true });
}

/** Types into a labelled box and proves it holds what was typed. */
async function type(page: Page, label: string, value: string): Promise<void> {
  const el = labelled(page, label);
  await el.fill(value);
  await expect(el, `"${label}" did not take what was typed into it`).toHaveValue(value);
}

/** Picks an option from a labelled `ui/Select`.
 *
 *  Not `choose` from the harness: that drives a native `<select>`, whose options
 *  belong to the browser. This one is a Radix listbox rendered in a portal at
 *  the end of the document, so it is opened, the option is pressed where it
 *  actually is, and the trigger is read back for what it now says. */
async function pick(page: Page, label: string, option: string): Promise<void> {
  const trigger = labelled(page, label);
  // Opened from the keyboard, and not because keyboard access is what is being
  // tested: Radix opens the listbox on *pointerdown* and puts its portal under
  // the cursor before the button comes back up, so a mouse press never delivers
  // a click to the trigger and the control looks untouched to anything watching
  // events — the coverage recorder included, which is how this was found.
  await trigger.focus();
  await trigger.press("Enter");
  await page.getByRole("option", { name: option, exact: true }).click();
  await expect(trigger, `"${label}" did not keep the option chosen`).toContainText(option);
}

/** Ticks a labelled checkbox and proves it is ticked. */
async function tick(page: Page, label: string): Promise<void> {
  const box = labelled(page, label);
  await box.click();
  await expect(box, `"${label}" did not switch on`).toBeChecked();
}

/** The step now on screen, by its own heading rather than by a counter. */
function step(page: Page, title: string): Locator {
  return page.getByRole("heading", { name: title, level: 3 });
}

const STEPS = [
  "Staying unblocked", "A second source", "Being told",
  "How much it fetches", "The optional extras",
];

test("a fresh install can skip every step and land on an app that works", async ({ page }) => {
  await useEmptyBackend(page);

  // A search of this test's own, rather than the one the guided run leaves
  // behind: the setup is offered from the scan step, and which specs ran before
  // this one must not decide whether it is reachable. The URL way because it is
  // the one that needs no network.
  await page.goto("/start");
  await press(page, "onboarding.next");
  await press(page, "onboarding.wayUrl");
  await fill(page, "profiles.url.name", "Setup walkthrough");
  await fill(page, "profiles.url.url",
    "https://www.immobiliare.it/vendita-case/milano/?criterio=rilevanza&prezzoMassimo=350000");
  await press(page, "profiles.url.save");
  await expect(page.getByRole("heading", { name: "Run the first scan" })).toBeVisible();

  // ── the setup is a control on that step, not a sentence about Settings ────
  await press(page, "onboarding.setup");
  await expect.poll(() => path(page)).toBe("/setup");
  await expect(page.getByRole("heading", { name: "Set up what you need" })).toBeVisible();

  // What the machine can be asked is stated, not asked. Whether browser
  // automation is installed depends on the machine running this, so the
  // assertion is that the answer is on the screen — the cookie is one this
  // database has certainly never held.
  await expect(page.getByText(/Browser automation is (not )?installed/)).toBeVisible();
  await expect(page.getByText("No cookie stored yet")).toBeVisible();
  await checkScreen(page, "the capability setup, first step");

  // ── five steps, five skips, and no step that will not let go ─────────────
  for (const title of STEPS) {
    await expect(step(page, title)).toBeVisible();
    // Equals, not small type under the button that keeps going: both are
    // buttons, both are on every step, and this walk is the proof that the
    // second of them is enough on its own.
    await expect(control(page, "setup.skip")).toBeEnabled();
    await press(page, "setup.skip");
  }

  // ── and what that lands on is the app, not a half-configured one ─────────
  await expect.poll(() => path(page)).toBe("/listings");
  await expect(cards(page)).toHaveCount(0);
  await press(page, "nav.searches");
  await expect(page.getByText("Setup walkthrough")).toBeVisible();
});

test("one answer per step, and every one of them is still there afterwards", async ({ page }) => {
  await useEmptyBackend(page);
  await page.goto("/listings");

  // ── the way back in, which is what stops this being a one-shot ───────────
  await press(page, "nav.settings");
  await expect.poll(() => path(page)).toBe("/settings");
  // Case-insensitive: the section headings in this dialog are uppercased by a
  // stylesheet, and what the test is about is the words, not the CSS.
  await expect(page.getByRole("heading", { name: /guided setup/i })).toBeVisible();
  // The previous test finished the setup against this same database, and the
  // flag it wrote lives with the settings rather than in this browser — so the
  // wording here is the assertion that it survived the reload, the second test
  // and, by the same mechanism, an upgrade.
  await expect(control(page, "settings.setup.open"))
    .toHaveText("Go through the setup again");
  await expect(page.getByText("These are still switched off:")).toBeVisible();
  await expect(page.getByText("Staying unblocked")).toBeVisible();

  await press(page, "settings.setup.open");
  await expect.poll(() => path(page)).toBe("/setup");

  // ── one answer per group, in the order the groups are asked ──────────────
  await expect(step(page, "Staying unblocked")).toBeVisible();
  await type(page, "Proxies", "http://proxy.example:8080");
  await type(page, "Scraping service key", "zk-e2e-key");
  await pick(page, "When to use it", "Every request");
  await press(page, "setup.save");

  await expect(step(page, "A second source")).toBeVisible();
  await type(page, "Idealista API key", "ik-e2e-key");
  await type(page, "Idealista API secret", "is-e2e-secret");
  await press(page, "setup.save");

  await expect(step(page, "Being told")).toBeVisible();
  await type(page, "Mail server", "smtp.example.invalid");
  await type(page, "Send to", "alerts@example.invalid");
  await tick(page, "Send me alerts by email");
  await press(page, "setup.save");

  await expect(step(page, "How much it fetches")).toBeVisible();
  await type(page, "Pages per search", "7");
  await press(page, "setup.save");

  await expect(step(page, "The optional extras")).toBeVisible();
  await type(page, "Geocoding server", "http://nominatim.example.invalid");
  await expect(control(page, "setup.save")).toHaveText("Save and finish");
  await press(page, "setup.save");
  await expect.poll(() => path(page)).toBe("/listings");

  // ── a full reload, so nothing below can be answered from memory ──────────
  await page.reload();
  await press(page, "nav.settings");
  await expect(page.getByText("Everything the guided setup offers is switched on."))
    .toBeVisible();
  await press(page, "settings.setup.open");

  // ── every answer, read back from the backend ─────────────────────────────
  await expect(step(page, "Staying unblocked")).toBeVisible();
  await expect(labelled(page, "Proxies")).toHaveValue("http://proxy.example:8080");
  await expect(labelled(page, "When to use it")).toContainText("Every request");
  // A secret is never sent back — the API answers "***" and the form refuses to
  // seed a box with it, since posting those three characters would overwrite the
  // key. So what proves the key arrived is the chip, and the box being empty is
  // half of the same proof.
  await expect(labelled(page, "Scraping service key")).toHaveValue("");
  await expect(page.getByText("Saved", { exact: true })).toHaveCount(1);

  await press(page, "setup.skip");
  await expect(step(page, "A second source")).toBeVisible();
  await expect(page.getByText("Saved", { exact: true })).toHaveCount(2);

  // Back, and the step before it is as it was left: a wizard that loses an
  // answer to a reconsidered step is one nobody presses Back in.
  await press(page, "setup.back");
  await expect(labelled(page, "Proxies")).toHaveValue("http://proxy.example:8080");
  await press(page, "setup.skip");

  await press(page, "setup.skip");
  await expect(step(page, "Being told")).toBeVisible();
  await expect(labelled(page, "Mail server")).toHaveValue("smtp.example.invalid");
  await expect(labelled(page, "Send to")).toHaveValue("alerts@example.invalid");
  await expect(labelled(page, "Send me alerts by email")).toBeChecked();
  // Only what was answered was written: the other channel on the same step was
  // left alone, and a step that posted its whole model would have switched it on
  // with an empty token.
  await expect(labelled(page, "Send me alerts on Telegram")).not.toBeChecked();

  await press(page, "setup.skip");
  await expect(step(page, "How much it fetches")).toBeVisible();
  await expect(labelled(page, "Pages per search")).toHaveValue("7");

  await press(page, "setup.skip");
  await expect(step(page, "The optional extras")).toBeVisible();
  await expect(labelled(page, "Geocoding server"))
    .toHaveValue("http://nominatim.example.invalid");

  // Skipping the last step still finishes, and finishing writes the flag on its
  // own — an unrelated save that must not take the keys with it.
  await press(page, "setup.skip");
  await expect.poll(() => path(page)).toBe("/listings");
  await press(page, "nav.settings");
  await expect(page.getByText("Everything the guided setup offers is switched on."))
    .toBeVisible();
});
