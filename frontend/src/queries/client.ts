/** The cache every read in this app goes through.
 *
 *  Four defaults, and each one is here to keep a behaviour the hand-rolled
 *  fetches already had rather than to adopt the library's opinion:
 *
 *  - **`retry: false`.** Every call used to go out once and report what came
 *    back. Retrying three times behind a spinner would turn a refused write into
 *    several seconds of nothing before the message the user actually needs, and
 *    on a loopback backend a request that failed will fail again.
 *  - **`refetchOnWindowFocus: false`.** Nothing here refetched on focus. Turning
 *    it on would mean a scan that appears to progress only when the tab is
 *    looked at, which is worse than one that visibly polls.
 *  - **`staleTime: 0`.** A read is only fresh while it is being watched — the
 *    grid, the panels and the progress endpoints all want the newest answer.
 *    The one read that must *not* be refetched behind the user's back is the
 *    settings form, and it says so at its own call site.
 *  - **`gcTime`.** Left at the library's five minutes: a filter the user backs
 *    out of should still be in hand when they come back to it.
 */
import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}
