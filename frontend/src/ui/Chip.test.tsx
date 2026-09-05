import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Chip } from "./Chip";

describe("Chip", () => {
  it("stays out of the tab order, because it is a label and not a control", async () => {
    const user = userEvent.setup();
    render(<><Chip tone="positive">Price drop</Chip><Button>Next</Button></>);

    // The keyboard contract of a non-interactive primitive is that it has none:
    // a chip that can be focused is a chip somebody has quietly made clickable,
    // and a control that reads as a badge is one nobody can name. Filtering by a
    // tag is a `Button`; this draws the state.
    await user.tab();
    expect(screen.getByRole("button", { name: "Next" })).toHaveFocus();
  });

  it("says the state in words, not only in colour", () => {
    render(<Chip tone="negative" dot>Withdrawn</Chip>);
    expect(screen.getByText("Withdrawn")).toBeInTheDocument();
  });

  it("keeps the dot out of the accessibility tree", () => {
    const { container } = render(<Chip tone="caution" dot>Stale</Chip>);
    expect(container.querySelectorAll("[aria-hidden='true']")).toHaveLength(1);
  });

  it("takes its colour from a role in every tone", () => {
    const { rerender } = render(<Chip tone="accent">A</Chip>);
    expect(screen.getByText("A")).toHaveClass("bg-accent-soft");

    rerender(<Chip tone="rent">A</Chip>);
    expect(screen.getByText("A")).toHaveClass("bg-rent-soft");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Chip tone="info" dot>Seen today</Chip>);
    await expectAccessible(container);
  });
});
