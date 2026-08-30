/** What every browser test imports instead of `@playwright/test`.
 *
 *  The only thing it adds today is the offline guard, applied automatically so
 *  no spec can forget it. Importing `test` from here rather than from the
 *  library is what makes that possible, and it is where the invariants the
 *  suite applies to *every* journey will go.
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
      if (guard.attempted.length > 0) {
        throw new Error(offlineViolation(guard.attempted));
      }
    },
    // `auto` so it runs for a test that never mentions it — an opt-in guard is
    // one the next spec forgets.
    { auto: true },
  ],
});

export { expect };
