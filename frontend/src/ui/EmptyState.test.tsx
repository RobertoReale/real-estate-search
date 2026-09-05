import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("hands the user the way out, reachable with one Tab", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <EmptyState
        title="No saved searches"
        description="Save a search to be told when something new matches it."
        action={<Button variant="solid" tone="accent" data-action="search.save" onClick={onClick}>
          Save this search
        </Button>} />,
    );

    await user.tab();
    expect(screen.getByRole("button", { name: "Save this search" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("keeps the caller's inventory id on the control", () => {
    render(
      <EmptyState title="Nothing yet"
        action={<Button data-action="search.save">Save</Button>} />,
    );
    // The action is a slot, so the button in the inventory is the caller's and
    // not one this component invented under a name that means nothing.
    expect(screen.getByRole("button")).toHaveAttribute("data-action", "search.save");
  });

  it("places itself in the outline at the level the caller asks for", () => {
    const { rerender } = render(<EmptyState title="Nothing yet" headingLevel={2} />);
    expect(screen.getByRole("heading", { level: 2, name: "Nothing yet" })).toBeInTheDocument();

    rerender(<EmptyState title="Nothing yet" />);
    expect(screen.getByRole("heading", { level: 3, name: "Nothing yet" })).toBeInTheDocument();
  });

  it("leaves the decorative icon out of the accessibility tree", () => {
    render(<EmptyState icon={<span>[]</span>} title="Nothing yet" />);
    expect(screen.getByText("[]").parentElement).toHaveAttribute("aria-hidden", "true");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <EmptyState
        icon={<span>[]</span>}
        title="No saved searches"
        description="Save a search to be told when something new matches it."
        action={<Button variant="solid" tone="accent">Save this search</Button>} />,
    );
    await expectAccessible(container);
  });
});
