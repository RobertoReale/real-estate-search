import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Button } from "./Button";

describe("Button", () => {
  it("is reached with Tab and fired with both Enter and Space", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);

    await user.tab();
    expect(screen.getByRole("button", { name: "Save" })).toHaveFocus();

    await user.keyboard("{Enter}");
    await user.keyboard(" ");
    // Both, because a `<div role="button">` answers to neither and a hand-rolled
    // one usually answers to exactly one.
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("is skipped by Tab and fires nothing when disabled", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<><Button disabled onClick={onClick}>Save</Button><Button>After</Button></>);

    await user.tab();
    expect(screen.getByRole("button", { name: "After" })).toHaveFocus();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("takes its emphasis from the declared variant, not from the caller's memory", () => {
    const { rerender } = render(<Button variant="solid" tone="accent">Go</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-accent");

    rerender(<Button variant="outline" tone="negative">Go</Button>);
    expect(screen.getByRole("button")).toHaveClass("text-negative-ink");

    rerender(<Button variant="ghost" tone="neutral">Go</Button>);
    expect(screen.getByRole("button")).not.toHaveClass("bg-accent");
  });

  it("defaults to type=button so a control inside a form does not submit it", () => {
    render(<Button>Filter</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("styles the child instead of nesting a button inside it", () => {
    render(<Button asChild variant="solid" tone="accent"><a href="/insights">Insights</a></Button>);

    const link = screen.getByRole("link", { name: "Insights" });
    expect(link).toHaveClass("rounded-control");
    expect(link).not.toHaveAttribute("type");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Button variant="solid" tone="accent">Save</Button>);
    await expectAccessible(container);
  });
});
