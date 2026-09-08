/** One screenshot per screen, at each of the three widths `checkScreen` already
 *  holds every journey to.
 *
 *  This is a pixel diff, not an assertion about behaviour — the coverage suite
 *  already owns that. What it catches is the thing nobody writes a `toBeVisible`
 *  for: a token that shifted a card's padding everywhere at once, a component
 *  that regressed only at 768px. The baseline lives beside this file
 *  (`visual.spec.ts-snapshots/`) and is platform-suffixed by Playwright itself,
 *  so it is only ever compared against a run on the same OS that made it — the
 *  CI job that owns this spec runs on Linux for exactly that reason.
 *
 *  The suffix says `linux` and that is not specific enough to write one by:
 *  the first set was made on a Linux that was not `ubuntu-latest`, and its
 *  slightly different glyph advances wrapped text a line earlier on every
 *  screen. Do not run this with `--update-snapshots`; regenerate on the runner
 *  that reads them, with the `Visual baselines` workflow.
 */
import { expect, type Page } from "@playwright/test";
import { settle, WIDTHS } from "./invariants";

const HEIGHT = 900;

export async function snapshotScreen(page: Page, name: string): Promise<void> {
  const original = page.viewportSize();

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: HEIGHT });
    await settle(page);
    await expect(page).toHaveScreenshot(`${name}-${width}.png`, { fullPage: true });
  }

  if (original) await page.setViewportSize(original);
}
