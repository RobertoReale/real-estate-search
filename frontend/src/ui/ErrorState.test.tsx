import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";
import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("announces itself, which is the whole difference from an empty one", () => {
    render(<ErrorState title="The results could not be loaded" />);
    // A reader who has already moved past the region is still told why it is
    // empty; `status` would wait for them to come back and find out.
    expect(screen.getByRole("alert")).toHaveTextContent("The results could not be loaded");
  });

  it("carries what the backend said, next to the way to ask again", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <ErrorState
        title="The results could not be loaded"
        description="Connection refused"
        action={<Button variant="solid" tone="accent" data-action="search.save" onClick={onClick}>
          Try again
        </Button>} />,
    );

    expect(screen.getByText("Connection refused")).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole("button", { name: "Try again" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("keeps the caller's inventory id on the retry", () => {
    render(
      <ErrorState title="Could not load"
        action={<Button data-action="search.save">Try again</Button>} />,
    );
    // The retry belongs to the surface that failed: it is asking for that
    // surface's data again, and it is inventoried under that name.
    expect(screen.getByRole("button")).toHaveAttribute("data-action", "search.save");
  });

  it("places itself in the outline at the level the caller asks for", () => {
    render(<ErrorState title="Could not load" headingLevel={2} />);
    expect(screen.getByRole("heading", { level: 2, name: "Could not load" })).toBeInTheDocument();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <ErrorState
        title="The results could not be loaded"
        description="Connection refused"
        action={<Button variant="solid" tone="accent">Try again</Button>} />,
    );
    await expectAccessible(container);
  });
});
