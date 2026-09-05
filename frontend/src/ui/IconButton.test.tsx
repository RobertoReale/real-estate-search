import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { IconButton } from "./IconButton";

const Cross = () => (
  <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3 fill-none stroke-current stroke-2">
    <path d="m2 2 8 8M10 2l-8 8" />
  </svg>
);

describe("IconButton", () => {
  it("is named by its label, which is the whole point of the component", () => {
    render(<IconButton label="Close the panel"><Cross /></IconButton>);

    // `label` is required in the type, so a nameless icon button cannot compile.
    // This asserts the label reaches the accessibility tree and the tooltip both.
    const button = screen.getByRole("button", { name: "Close the panel" });
    expect(button).toHaveAttribute("title", "Close the panel");
  });

  it("is reached with Tab and fired from the keyboard", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<IconButton label="Close" onClick={onClick}><Cross /></IconButton>);

    await user.tab();
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is square at both sizes, so the icon is not squeezed by a text padding", () => {
    const { rerender } = render(<IconButton label="Close" size="sm"><Cross /></IconButton>);
    expect(screen.getByRole("button")).toHaveClass("h-8", "w-8");

    rerender(<IconButton label="Close" size="md"><Cross /></IconButton>);
    expect(screen.getByRole("button")).toHaveClass("h-10", "w-10");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<IconButton label="Close"><Cross /></IconButton>);
    await expectAccessible(container);
  });
});
