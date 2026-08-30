/** What the suite actually fired, collected from the browser rather than claimed.
 *
 *  The static gate (`harness/jsx.ts`) proves every control has an identity. This
 *  proves each identity was used: an init script watches the page for the events
 *  the inventory is written against and writes down which `data-action` they
 *  reached, every test appends its haul to a file, and the last spec in the run
 *  fails on any inventory row that never appeared. A control cannot be quietly
 *  added and left untested, because the second gate reads what the browser saw
 *  and not what a test says it did.
 *
 *  Two decisions worth knowing about:
 *
 *  1. **The nearest declared ancestor wins.** `closest("[data-action]")`, not
 *     the whole path — clicking the star inside a card must credit the star and
 *     not the card underneath it, whose own handler `stopPropagation` prevents
 *     from ever running.
 *  2. **Except for the guards.** An element declared `guard` in the inventory
 *     exists precisely to intercept events on their way past, so it *is* run by
 *     every event that crosses it, and it is credited for them. The list comes
 *     from the inventory rather than from a rule in here, so the two cannot
 *     drift apart.
 *
 *  The recording is appended to a per-run directory rather than kept in memory:
 *  the coverage gate runs as its own Playwright project, in a second worker
 *  process, and a variable in this one would be invisible to it.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));

/** Beside the throwaway databases in `frontend/.e2e-data/`, which is where the
 *  run's scratch already lives and the one path `.gitignore` covers. Wiped at
 *  the start of every run by the global setup. */
export const RECORD_DIR = path.join(HERE, "..", "..", ".e2e-data", "actions");

/** Where the page keeps its running list. `sessionStorage`, not a variable on
 *  `window`: several of the controls being recorded end in a reload — the
 *  restart, the three resets, the reload on the last-resort error screen — and
 *  a variable would be swept away by the very action that had just been fired,
 *  leaving those looking untested when they were the opposite. */
const KEY = "__firedActions";

/** Arms the page. Must be installed before the first navigation — an init
 *  script runs on every document the page loads, so a reload keeps recording
 *  into the same list rather than starting a new one. */
export async function installRecorder(page: Page, guards: readonly string[]): Promise<void> {
  await page.addInitScript(([storageKey, guardIds]: [string, string[]]) => {
    const guarded = new Set(guardIds);
    const read = (): string[] => {
      try {
        return JSON.parse(sessionStorage.getItem(storageKey) ?? "[]") as string[];
      } catch {
        return [];
      }
    };

    const note = (event: Event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const fired: string[] = [];
      const nearest = target.closest<HTMLElement>("[data-action]");
      if (nearest?.dataset.action) fired.push(nearest.dataset.action);
      // The guards above it ran too, whatever stopped the event afterwards.
      for (
        let el: HTMLElement | null = nearest?.parentElement ?? (target.parentElement as HTMLElement | null);
        el;
        el = el.parentElement
      ) {
        const id = el.dataset?.action;
        if (id && guarded.has(id)) fired.push(id);
      }
      if (fired.length === 0) return;
      sessionStorage.setItem(storageKey, JSON.stringify([...new Set([...read(), ...fired])]));
    };

    // Capture phase, on the window: React attaches its own listeners to the
    // root container and simulates propagation from there, so a handler that
    // calls `stopPropagation` would hide the event from a bubbling listener
    // here. Capture sees it on the way down, before any of that.
    for (const type of ["click", "change", "submit", "keydown"]) {
      window.addEventListener(type, note, true);
    }
  }, [KEY, [...guards]] as [string, string[]]);
}

/** Drains what this page has recorded so far and forgets it. */
export async function harvest(page: Page): Promise<string[]> {
  if (page.isClosed()) return [];
  try {
    return await page.evaluate((storageKey) => {
      const seen = sessionStorage.getItem(storageKey);
      sessionStorage.removeItem(storageKey);
      return seen ? (JSON.parse(seen) as string[]) : [];
    }, KEY);
  } catch {
    // A page navigating (or a context tearing down) while this runs is not a
    // failure of the test that just passed; the ids are re-recorded next time
    // the action is fired, and the coverage gate is what reports a real gap.
    return [];
  }
}

/** One file per test, named so two tests cannot collide. */
export function writeRecording(label: string, ids: readonly string[]): void {
  if (ids.length === 0) return;
  fs.mkdirSync(RECORD_DIR, { recursive: true });
  const safe = label.replace(/[^a-z0-9]+/gi, "-").slice(0, 80);
  fs.writeFileSync(
    path.join(RECORD_DIR, `${safe}-${process.pid}-${Date.now()}.json`),
    JSON.stringify([...new Set(ids)].sort(), null, 0),
  );
}

/** Everything the whole run fired, read back by the coverage gate. */
export function readRecordings(): Set<string> {
  const all = new Set<string>();
  if (!fs.existsSync(RECORD_DIR)) return all;
  for (const name of fs.readdirSync(RECORD_DIR)) {
    if (!name.endsWith(".json")) continue;
    for (const id of JSON.parse(fs.readFileSync(path.join(RECORD_DIR, name), "utf8")) as string[]) {
      all.add(id);
    }
  }
  return all;
}
