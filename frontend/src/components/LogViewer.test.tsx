/** A log tail that arrives late must not land on top of a newer one.
 *
 * The viewer used to start a fetch per effect run and guard the result with a
 * `cancelled` flag — and the early return for "auto-refresh off" sat above the
 * cleanup, so that run registered none at all and its flag was never set. A tail
 * still in flight when the effect re-ran resolved anyway and wrote itself over
 * whatever the newer run had already fetched. On a backend slow enough to make
 * anyone reach for the log viewer, that is the older tail winning.
 *
 * The guard is now the shape of the read rather than a flag: one query key means
 * one request in flight, so a second tick while a tail is in the air joins the
 * request already made instead of starting a rival. That is what these assert —
 * the requests never stack, and the newest answer is the one on screen.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import LogViewer from "./LogViewer";
import { api } from "../services/api";
import { WithQuery } from "../test/withQuery";

// jsdom has no layout, so it does not implement scrollIntoView; the viewer
// calls it to stay pinned to the newest line.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// The tail refreshes on a timer, so the clock is what drives these. Testing
// Library's async helpers need the real clock to keep turning underneath it.
beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => vi.useRealTimers());

type Tail = Awaited<ReturnType<typeof api.logsTail>>;

/** Hands back the resolvers of every tail asked for, so a test can answer them
 *  in whatever order it wants to prove something about. */
function deferredTails(): ((tail: Tail) => void)[] {
  const pending: ((tail: Tail) => void)[] = [];
  vi.spyOn(api, "logsTail").mockImplementation(
    () => new Promise<Tail>((resolve) => pending.push(resolve)),
  );
  return pending;
}

describe("the log viewer's tail", () => {
  it("never has two in the air at once, so an older one cannot win", async () => {
    const pending = deferredTails();
    render(<WithQuery><LogViewer onClose={vi.fn()} /></WithQuery>);
    await waitFor(() => expect(pending).toHaveLength(1));

    // Two refresh intervals pass while the first tail is still unanswered. It
    // must not have started a second: that is the collision this used to lose.
    await act(() => vi.advanceTimersByTimeAsync(7000));
    expect(pending).toHaveLength(1);

    await act(async () => { pending[0]({ lines: ["FIRST"], path: "app.log" }); });
    await waitFor(() => expect(screen.getByText("FIRST")).toBeInTheDocument());

    // and the next tick does ask again, with the newer answer replacing it
    await act(() => vi.advanceTimersByTimeAsync(3100));
    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => { pending[1]({ lines: ["SECOND"], path: "app.log" }); });

    await waitFor(() => expect(screen.getByText("SECOND")).toBeInTheDocument());
    expect(screen.queryByText("FIRST")).toBeNull();
  });

  it("stops asking when auto-refresh is turned off, and keeps what it has", async () => {
    const pending = deferredTails();
    render(<WithQuery><LogViewer onClose={vi.fn()} /></WithQuery>);
    await waitFor(() => expect(pending).toHaveLength(1));
    await act(async () => { pending[0]({ lines: ["ONLY"], path: "app.log" }); });
    await waitFor(() => expect(screen.getByText("ONLY")).toBeInTheDocument());

    const autoRefresh = screen.getByRole("checkbox") as HTMLInputElement;
    await act(async () => { autoRefresh.click(); });

    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(pending).toHaveLength(1);
    expect(screen.getByText("ONLY")).toBeInTheDocument();
  });
});
