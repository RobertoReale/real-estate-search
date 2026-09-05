/** What a failure turns into on screen.
 *
 * The regression this guards is the one the whole toast system exists to fix:
 * every surface used to print `e.message` and stop there, so "Failed to fetch"
 * — a backend that is not running — read exactly like a request the backend had
 * considered and refused. The two need different answers, and the only thing
 * that can tell them apart is the shape of the error, not its words.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider, adviceFor, errorText, useToasts } from "./Toast";
import { ApiError } from "../services/api";

/** Raises one toast on mount, so the assertions are about what is drawn rather
 *  than about the hook's return value. */
function Raise({ error, retry }: { error: unknown; retry?: () => void }) {
  const toasts = useToasts();
  return (
    <button onClick={() => toasts.fail(error, { doing: "The star did not stick.", retry })}>
      go
    </button>
  );
}

describe("what to do about a failure", () => {
  it("tells a backend that never answered apart from one that refused", () => {
    expect(adviceFor(new ApiError(0, "Failed to fetch"))).toMatch(/start\.bat/);
    expect(adviceFor(new ApiError(500, "boom"))).toMatch(/log|problem|problema/i);
    expect(adviceFor(new ApiError(422, "no"))).toMatch(/refus|rifiut/i);
    // Not an answer at all — a bug in the app, or a promise that rejected with
    // something that was never an HTTP call.
    expect(adviceFor(new Error("undefined is not a function"))).toMatch(/again|Riprova/i);
  });

  it("keeps the provider's own words for the two failures a user can act on", () => {
    expect(errorText(new Error("535 5.7.8 Username and Password not accepted")))
      .toMatch(/535/);
    expect(errorText(new Error("nothing special"))).toBe("nothing special");
  });
});

describe("the message a failure raises", () => {
  it("says what failed, what the backend said, and what to do", async () => {
    render(
      <ToastProvider>
        <Raise error={new ApiError(503, "the database is locked")} />
      </ToastProvider>,
    );
    screen.getByRole("button", { name: "go" }).click();

    const message = await screen.findByRole("alert");
    expect(message.textContent).toContain("The star did not stick.");
    expect(message.textContent).toContain("the database is locked");
    expect(message.textContent).toMatch(/log|problem|problema/i);
  });

  it("runs the retry once and takes the message away with it", async () => {
    const retry = vi.fn();
    render(
      <ToastProvider>
        <Raise error={new ApiError(503, "boom")} retry={retry} />
      </ToastProvider>,
    );
    screen.getByRole("button", { name: "go" }).click();

    (await screen.findByRole("button", { name: /try again|riprova/i })).click();

    await waitFor(() => expect(retry).toHaveBeenCalledTimes(1));
    // Gone before the retry lands: a message about what already happened,
    // still on screen, invites a second press of the same button.
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });
});
