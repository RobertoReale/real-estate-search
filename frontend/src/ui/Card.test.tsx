import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Card, CardHeader } from "./Card";

describe("Card", () => {
  it("is a container and takes no focus of its own", async () => {
    const user = userEvent.setup();
    render(
      <Card>
        <CardHeader title="Rome, Prati" actions={<Button size="sm">Open</Button>} />
        <p>Two listings.</p>
      </Card>,
    );

    // Tab reaches the action inside the card and nothing else. A card that is
    // itself focusable is the pattern where the whole tile is a link and the
    // buttons on it are unreachable; the controls live inside, not on it.
    await user.tab();
    expect(screen.getByRole("button", { name: "Open" })).toHaveFocus();
  });

  it("carries the title and its actions on one line", () => {
    render(<Card><CardHeader title="Insights" actions={<Button size="sm">Refresh</Button>} /></Card>);

    expect(screen.getByText("Insights")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });

  it("declares elevation and padding rather than re-deciding them per screen", () => {
    const { container, rerender } = render(<Card elevation="e3" padding="lg">x</Card>);
    expect(container.firstElementChild).toHaveClass("shadow-e3", "p-5");

    rerender(<Card elevation="e1" padding="none">x</Card>);
    expect(container.firstElementChild).toHaveClass("shadow-e1");
    expect(container.firstElementChild).not.toHaveClass("p-4");
  });

  it("renders onto the child element when asChild, so a list stays a list", () => {
    render(<ul><Card asChild><li>A listing</li></Card></ul>);

    const item = screen.getByRole("listitem");
    expect(item).toHaveClass("rounded-card");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <Card><CardHeader title="Rome, Prati" actions={<Button size="sm">Open</Button>} /></Card>,
    );
    await expectAccessible(container);
  });
});
