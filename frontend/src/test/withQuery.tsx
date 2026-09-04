/** A component tree with its own cache, for the tests that render one.
 *
 *  Every test gets a *fresh* client: the cache is shared server state, and one
 *  left over from a previous test would answer the next one's first render from
 *  data it never asked for — which reads as a component that renders before its
 *  fetch resolves, and passes for the wrong reason.
 *
 *  Retries off, matching the application's own default (`queries/client.ts`).
 *  A test that mocks a rejection wants the rejection, not three of them.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactElement, ReactNode } from "react";

export function newQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

/** Wraps a tree in a fresh cache. Built through an initializer, not inline: a
 *  client constructed in the render body is a new empty cache on every render,
 *  which is a subtler bug than having no provider at all. */
export function WithQuery({ children }: { children: ReactNode }): ReactElement {
  const [client] = useState(newQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
