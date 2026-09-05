import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Dialog } from "./Dialog";

function Stateful() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Delete the search</Button>
      <Dialog open={open} onOpenChange={setOpen}
        title="Delete this saved search?"
        description="The alerts it raises stop with it."
        closeLabel="Close"
        footer={<Button variant="solid" tone="negative" onClick={() => setOpen(false)}>
          Delete
        </Button>}>
        <p>This cannot be undone.</p>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("opens from the keyboard and gives the dialog its title as a name", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAccessibleName("Delete this saved search?");
    expect(dialog).toHaveAccessibleDescription("The alerts it raises stop with it.");
  });

  it("keeps Tab inside itself while it is open", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    const opener = screen.getByRole("button", { name: "Delete the search" });
    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    const inside = [
      screen.getByRole("button", { name: "Close" }),
      screen.getByRole("button", { name: "Delete" }),
    ];

    // Three Tabs around a two-control dialog must come back to where it started.
    // Without a trap the third lands on the page behind, and the user is typing
    // into something they cannot see.
    for (let i = 0; i < 3; i += 1) {
      await user.tab();
      expect(inside).toContain(document.activeElement);
    }
    expect(opener).not.toHaveFocus();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("returns focus to the control that opened it", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    const opener = screen.getByRole("button", { name: "Delete the search" });
    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");

    // Restored on the frame after the content unmounts, which is why this waits:
    // a dialog that closes and leaves focus on `<body>` costs the keyboard user
    // their place in the page.
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("names the close button in the caller's words", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    // `closeLabel` is required in the type, so an untranslated dialog is a
    // compile error rather than a cross a screen reader calls "button".
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("carries no description when there is nothing to add to the title", async () => {
    render(
      <Dialog open onOpenChange={vi.fn()} title="Delete this saved search?" closeLabel="Close">
        <p>This cannot be undone.</p>
      </Dialog>,
    );

    expect(await screen.findByRole("dialog")).not.toHaveAttribute("aria-describedby");
  });

  it("has no accessibility violations", async () => {
    render(
      <Dialog open onOpenChange={vi.fn()} title="Delete this saved search?"
        description="The alerts it raises stop with it." closeLabel="Close">
        <p>This cannot be undone.</p>
      </Dialog>,
    );

    await screen.findByRole("dialog");
    // The dialog renders into a portal, so the assertion is on the document.
    await expectAccessible(document.body);
  });
});
