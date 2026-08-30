/** What every browser test imports instead of `@playwright/test`.
 *
 *  Two things come with it, both applied automatically so no spec can forget
 *  them: the offline guard, and the per-screen invariants every journey is held
 *  to (`checkScreen`, re-exported here so a spec needs one import). Importing
 *  `test` from here rather than from the library is what makes that possible.
 */
import { test as base, expect } from "@playwright/test";
import type { OfflineGuard } from "./harness/offline";
import { installOfflineGuard, offlineViolation } from "./harness/offline";

// Not named `offline`: that is already a Playwright context option (it puts the
// browser in offline mode), and a fixture of that name would shadow it rather
// than add to it.
export const test = base.extend<{ offlineGuard: OfflineGuard }>({
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
});

export { checkScreen } from "./harness/invariants";
export { expect };
