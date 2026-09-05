import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { IconButton } from "./IconButton";
import { Tooltip } from "./Tooltip";

const Star = () => <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3" />;

function Favourite() {
  return (
    <Tooltip label="Save to favourites">
      <IconButton label="Save to favourites"><Star /></IconButton>
    </Tooltip>
  );
}

describe("Tooltip", () => {
  it("appears on focus, not only on hover", async () => {
    const user = userEvent.setup();
    render(<Favourite />);

    await user.tab();
    expect(screen.getByRole("button", { name: "Save to favourites" })).toHaveFocus();
    // A tooltip that only answers to a pointer is a label half the users never
    // see. Radix opens on focus with no delay; this asserts we get that.
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Save to favourites");
  });

  it("closes on Escape without moving focus", async () => {
    const user = userEvent.setup();
    render(<Favourite />);

    await user.tab();
    await screen.findByRole("tooltip");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).toBeNull();
    expect(screen.getByRole("button", { name: "Save to favourites" })).toHaveFocus();
  });

  it("goes away when focus leaves the trigger", async () => {
    const user = userEvent.setup();
    render(<><Favourite /><IconButton label="After"><Star /></IconButton></>);

    await user.tab();
    await screen.findByRole("tooltip");

    await user.tab();
    expect(screen.getByRole("button", { name: "After" })).toHaveFocus();
    expect(screen.queryByRole("tooltip")).toBeNull();
  });

  it("mounts its own provider, so it cannot be used outside one", () => {
    // A Radix tooltip without a provider throws at render. The provider is
    // inside the component precisely so this renders on its own.
    expect(() => render(<Favourite />)).not.toThrow();
  });

  it("has no accessibility violations", async () => {
    const user = userEvent.setup();
    render(<Favourite />);

    await user.tab();
    await screen.findByRole("tooltip");
    await expectAccessible(document.body);
  });
});
