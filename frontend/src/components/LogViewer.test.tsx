/** A log tail from a torn-down effect must not land on the screen.
 *
 * The effect returned early when auto-refresh was off — above its own cleanup,
 * so it registered none. Its `cancelled` flag was therefore never set, and a
 * tail still in flight when the effect re-ran (auto-refresh toggled back on,
 * the language switched, or the dialog closed) resolved anyway and wrote itself
 * over whatever the newer run had already fetched. On a backend slow enough to
 * make anyone reach for the log viewer, that is the older tail winning.
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import LogViewer from "./LogViewer";
import { api } from "../services/api";

// jsdom has no layout, so it does not implement scrollIntoView; the viewer
// calls it to stay pinned to the newest line.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

type Tail = Awaited<ReturnType<typeof api.logsTail>>;

describe("LogViewer teardown", () => {
  it("drops the tail of an effect that has already been torn down", async () => {
    const pending: ((tail: Tail) => void)[] = [];
    vi.spyOn(api, "logsTail").mockImplementation(
      () => new Promise<Tail>((resolve) => pending.push(resolve)),
    );

    render(<LogViewer onClose={vi.fn()} />);
    await waitFor(() => expect(pending).toHaveLength(1));
    const autoRefresh = screen.getByRole("checkbox") as HTMLInputElement;

    // off, then on: the middle run is the one that had no cleanup
    await act(async () => { autoRefresh.click(); });
    await waitFor(() => expect(pending).toHaveLength(2));
    await act(async () => { autoRefresh.click(); });
    await waitFor(() => expect(pending).toHaveLength(3));

    // the current run answers first, then the abandoned one answers late
    await act(async () => { pending[2]({ lines: ["CURRENT"], path: "app.log" }); });
    await act(async () => { pending[1]({ lines: ["ABANDONED"], path: "app.log" }); });

    expect(screen.getByText("CURRENT")).toBeInTheDocument();
    expect(screen.queryByText("ABANDONED")).toBeNull();
  });
});
