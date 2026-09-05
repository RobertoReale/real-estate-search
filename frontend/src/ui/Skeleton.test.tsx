import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("is invisible to the keyboard and to a reader when it is only a placeholder", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <><Skeleton className="h-4 w-32" lines={3} /><Button>Retry</Button></>,
    );

    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
    await user.tab();
    expect(screen.getByRole("button", { name: "Retry" })).toHaveFocus();
  });

  it("announces the wait when it is the whole surface", () => {
    render(<Skeleton lines={4} label="Loading the listings" />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    // Said once. The boxes themselves stay hidden, or the reader recites one
    // line of nothing per placeholder.
    expect(status.textContent).toBe("Loading the listings");
  });

  it("draws one block per line, with the last one short", () => {
    const { container } = render(<Skeleton lines={3} className="h-4" />);
    const blocks = container.querySelectorAll(".animate-pulse");
    expect(blocks).toHaveLength(3);
    expect(blocks[2]).toHaveClass("w-2/3");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Skeleton lines={2} label="Loading the listings" />);
    await expectAccessible(container);
  });
});
