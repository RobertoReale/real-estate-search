import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEvent } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Input, Textarea } from "./Input";

describe("Input", () => {
  it("types, selects and clears from the keyboard alone", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Input aria-label="Search" onChange={onChange} />);

    await user.tab();
    const input = screen.getByRole("textbox", { name: "Search" });
    expect(input).toHaveFocus();

    await user.keyboard("Trastevere");
    expect(input).toHaveValue("Trastevere");

    await user.keyboard("{Control>}a{/Control}{Backspace}");
    expect(input).toHaveValue("");
    expect(onChange).toHaveBeenCalled();
  });

  it("submits the form it is in when Enter is pressed", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((event: FormEvent) => event.preventDefault());
    render(<form onSubmit={onSubmit}><Input aria-label="Search" /></form>);

    await user.tab();
    await user.keyboard("Rome{Enter}");
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("is skipped by Tab when disabled", async () => {
    const user = userEvent.setup();
    render(<><Input aria-label="Search" disabled /><Input aria-label="After" /></>);

    await user.tab();
    expect(screen.getByRole("textbox", { name: "After" })).toHaveFocus();
  });

  it("stands alone with its own name, without needing a Field around it", () => {
    render(<Input aria-label="Search" placeholder="Municipality, area…" />);
    expect(screen.getByRole("textbox", { name: "Search" })).toBeInTheDocument();
  });

  it("keeps the caller's attributes over the ones it derives", () => {
    render(<Input aria-label="Search" id="explicit" />);
    expect(screen.getByRole("textbox", { name: "Search" })).toHaveAttribute("id", "explicit");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Input aria-label="Search" />);
    await expectAccessible(container);
  });
});

describe("Textarea", () => {
  it("takes multiple lines from the keyboard", async () => {
    const user = userEvent.setup();
    render(<Textarea aria-label="Notes" />);

    await user.tab();
    await user.keyboard("First{Enter}Second");
    expect(screen.getByRole("textbox", { name: "Notes" })).toHaveValue("First\nSecond");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Textarea aria-label="Notes" />);
    await expectAccessible(container);
  });
});
