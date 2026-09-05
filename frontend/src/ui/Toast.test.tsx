import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Toast, ToastProvider, ToastViewport } from "./Toast";

function Raised({ onUndo, tone = "done" }: {
  onUndo?: () => void;
  tone?: "done" | "error";
}) {
  const [open, setOpen] = useState(true);
  return (
    <ToastProvider label="Notifications">
      <Toast open={open} onOpenChange={setOpen} tone={tone}
        title="Two listings hidden"
        description="They will stop appearing in this search."
        action={onUndo && { label: "Undo", altText: "Undo hiding two listings", onSelect: onUndo }}
        closeLabel="Dismiss"
        duration={Infinity} />
      <ToastViewport label="Messages ({hotkey})" />
    </ToastProvider>
  );
}

describe("Toast", () => {
  it("says what happened and what it means", () => {
    render(<Raised />);

    expect(screen.getByText("Two listings hidden")).toBeInTheDocument();
    expect(screen.getByText("They will stop appearing in this search.")).toBeInTheDocument();
  });

  it("interrupts for a failure and waits for a pause after a confirmation", async () => {
    const { unmount } = render(<Raised />);
    expect(await screen.findByRole("status")).toHaveAttribute("aria-live", "polite");
    unmount();

    // The live region is Radix's, and `type` is what chooses its politeness: a
    // failure cuts in, a confirmation queues behind whatever is being read.
    render(<Raised tone="error" />);
    expect(await screen.findByRole("status")).toHaveAttribute("aria-live", "assertive");
  });

  it("puts the undo within reach of the keyboard", async () => {
    const user = userEvent.setup();
    const onUndo = vi.fn();
    render(<Raised onUndo={onUndo} />);

    // The whole reason this is a Radix toast. A message appears without the user
    // asking, so it must not steal focus — which leaves the Undo on it
    // unreachable unless something takes the keyboard to the stack. F8 does, and
    // the region says so in its own name.
    // Dispatched directly because user-event's key map stops at the keys a
    // document normally reacts to and has no entry for the function row, so
    // `{F8}` arrives with an unknown `code` and Radix's listener — which matches
    // on `code` — never sees it.
    const region = screen.getByRole("region", { name: "Messages (F8)" });
    fireEvent.keyDown(document, { key: "F8", code: "F8" });
    expect(region).toContainElement(document.activeElement as HTMLElement);

    const undo = screen.getByRole("button", { name: "Undo" });
    for (let i = 0; i < 4 && document.activeElement !== undo; i += 1) await user.tab();
    expect(undo).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(onUndo).toHaveBeenCalledTimes(1);
  });

  it("is dismissed by the close button, in the caller's words", async () => {
    const user = userEvent.setup();
    render(<Raised onUndo={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Two listings hidden")).toBeNull();
  });

  it("has no accessibility violations", async () => {
    render(<Raised onUndo={vi.fn()} />);
    await screen.findByRole("region", { name: "Messages (F8)" });
    await expectAccessible(document.body);
  });
});
