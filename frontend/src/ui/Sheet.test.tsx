import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Sheet } from "./Sheet";

function Stateful({ side }: { side?: "right" | "left" | "bottom" }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Filters</Button>
      <Sheet open={open} onOpenChange={setOpen} side={side}
        title="Filters" description="Applied as you change them." closeLabel="Close">
        <Button>Reset</Button>
      </Sheet>
    </>
  );
}

describe("Sheet", () => {
  it("is a dialog that arrives from an edge, and is operated like one", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");

    const sheet = await screen.findByRole("dialog");
    expect(sheet).toHaveAccessibleName("Filters");
    expect(sheet).toHaveAccessibleDescription("Applied as you change them.");
  });

  it("closes on Escape and hands focus back", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    const opener = screen.getByRole("button", { name: "Filters" });
    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("keeps Tab among its own controls", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    const inside = [
      screen.getByRole("button", { name: "Close" }),
      screen.getByRole("button", { name: "Reset" }),
    ];
    for (let i = 0; i < 3; i += 1) {
      await user.tab();
      expect(inside).toContain(document.activeElement);
    }
  });

  it("arrives from the side the caller asks for", async () => {
    const user = userEvent.setup();
    render(<Stateful side="bottom" />);

    await user.tab();
    await user.keyboard("{Enter}");
    // The bottom sheet is the phone shape: full width, rounded at the top only.
    expect(await screen.findByRole("dialog")).toHaveClass("rounded-t-surface");
  });

  it("has no accessibility violations", async () => {
    render(
      <Sheet open onOpenChange={vi.fn()} title="Filters"
        description="Applied as you change them." closeLabel="Close">
        <Button>Reset</Button>
      </Sheet>,
    );

    await screen.findByRole("dialog");
    await expectAccessible(document.body);
  });
});
