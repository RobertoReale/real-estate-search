/** The "New" badge threshold, and why it is memoised.
 *
 * It is read from a `useState` initializer, and StrictMode invokes those twice
 * on mount. The reader also *writes* — it advances the stored "last seen"
 * timestamp — so when the read and the write both lived in the initializer, the
 * second invocation read back what the first had just written and the threshold
 * became "now". Every card then looked older than the threshold and none was
 * ever badged. Only in development: the production build has no double
 * invocation, so the one place the feature could be checked was the one place
 * it did not work.
 */

import { StrictMode, useState } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const KEY = "propertiesSeenBefore";

/** A fresh copy of the module, since the memo lives at module scope. */
async function freshReader() {
  vi.resetModules();
  return (await import("./App")).readSeenThreshold;
}

function Probe({ read }: { read: () => string | null }) {
  const [threshold] = useState<string | null>(read);
  return <span data-testid="threshold">{threshold ?? "NONE"}</span>;
}

describe("readSeenThreshold", () => {
  beforeEach(() => localStorage.clear());

  it("survives StrictMode's double invocation of the initializer", async () => {
    localStorage.setItem(KEY, "2026-01-01T00:00:00.000Z");
    const read = await freshReader();

    render(<StrictMode><Probe read={read} /></StrictMode>);

    expect(screen.getByTestId("threshold").textContent).toBe("2026-01-01T00:00:00.000Z");
  });

  it("still advances the stored timestamp, so a reload starts a new session", async () => {
    localStorage.setItem(KEY, "2026-01-01T00:00:00.000Z");
    const read = await freshReader();

    read();

    const stored = localStorage.getItem(KEY);
    expect(stored).not.toBe("2026-01-01T00:00:00.000Z");
    expect(Date.parse(stored ?? "")).toBeGreaterThan(Date.parse("2026-01-01T00:00:00.000Z"));
  });

  it("reports no threshold on a first-ever run, so nothing is badged", async () => {
    const read = await freshReader();
    expect(read()).toBeNull();
    // and it has claimed the key, so the next run has one
    expect(localStorage.getItem(KEY)).not.toBeNull();
  });
});
