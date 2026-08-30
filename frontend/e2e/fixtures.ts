/** What every browser test imports instead of `@playwright/test`.
 *
 *  Three things come with it, all applied automatically so no spec can forget
 *  them: the offline guard, the per-screen invariants every journey is held to
 *  (`checkScreen`, re-exported here so a spec needs one import), and the action
 *  recorder that feeds A.5's coverage gate. Importing `test` from here rather
 *  than from the library is what makes that possible.
 */
import { test as base, expect } from "@playwright/test";
import { GUARD_IDS } from "./actions";
import type { OfflineGuard } from "./harness/offline";
import { installOfflineGuard, offlineViolation } from "./harness/offline";
import { harvest, installRecorder, writeRecording } from "./harness/recorder";

// Not named `offline`: that is already a Playwright context option (it puts the
// browser in offline mode), and a fixture of that name would shadow it rather
// than add to it.
export const test = base.extend<{ offlineGuard: OfflineGuard; recordActions: void }>({
  offlineGuard: [
    async ({ context }, use) => {
      const guard = await installOfflineGuard(context);
      await use(guard);
      // `unexpected`, not `attempted`: a spec may declare an address it knows
      // will be blocked (the map's tiles), and that declaration is the whole
      // difference between testing the offline case and tripping over it.
      if (guard.unexpected.length > 0) {
        throw new Error(offlineViolation(guard.unexpected));
      }
    },
    // `auto` so it runs for a test that never mentions it — an opt-in guard is
    // one the next spec forgets.
    { auto: true },
  ],

  // Every test contributes to the inventory's coverage, not only the ones
  // written for it: a journey that favourites a property is as good a proof
  // that `property.favorite` works as a purpose-built press would be.
  recordActions: [
    async ({ page }, use, testInfo) => {
      await installRecorder(page, GUARD_IDS);
      await use();
      writeRecording(testInfo.titlePath.join("-"), await harvest(page));
    },
    { auto: true },
  ],
});

export { checkScreen } from "./harness/invariants";
export { expect };
