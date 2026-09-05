import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Popover } from "./Popover";

function Provenance() {
  return (
    <Popover label="Where this listing came from" trigger={<Button>Where from?</Button>}>
      <p>Seen on two portals, last checked an hour ago.</p>
      <a href="/sources">All the sources</a>
    </Popover>
  );
}

describe("Popover", () => {
  it("opens from the keyboard and moves focus into the panel", async () => {
    const user = userEvent.setup();
    render(<Provenance />);

    await user.tab();
    expect(screen.getByRole("button", { name: "Where from?" })).toHaveFocus();

    await user.keyboard("{Enter}");
    const panel = await screen.findByRole("dialog", { name: "Where this listing came from" });
    // Unlike a tooltip: the content is reachable, so a link inside it is a link
    // a keyboard user can follow.
    expect(panel).toContainElement(screen.getByRole("link", { name: "All the sources" }));
  });

  it("wires the trigger to the panel it controls", async () => {
    const user = userEvent.setup();
    render(<Provenance />);

    const trigger = screen.getByRole("button", { name: "Where from?" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("closes on Escape and returns focus to the trigger", async () => {
    const user = userEvent.setup();
    render(<Provenance />);

    const trigger = screen.getByRole("button", { name: "Where from?" });
    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("keeps the trigger's own styling and id when it renders it", () => {
    render(
      <Popover label="Where this listing came from"
        trigger={<Button data-action="detail.provenance" variant="ghost">Where from?</Button>}>
        <p>Detail.</p>
      </Popover>,
    );

    expect(screen.getByRole("button", { name: "Where from?" }))
      .toHaveAttribute("data-action", "detail.provenance");
  });

  it("has no accessibility violations", async () => {
    const user = userEvent.setup();
    render(<Provenance />);

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("dialog");
    await expectAccessible(document.body);
  });
});
