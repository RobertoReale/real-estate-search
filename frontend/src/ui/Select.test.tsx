import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Field } from "./Field";
import { Select, type SelectOption } from "./Select";

const OPTIONS: SelectOption[] = [
  { value: "sale", label: "For sale" },
  { value: "rent", label: "To rent" },
  { value: "auction", label: "At auction", disabled: true },
];

function Stateful({ label = "Contract" }: { label?: string }) {
  const [value, setValue] = useState("");
  return (
    <Select value={value} onValueChange={setValue} options={OPTIONS}
      placeholder="Choose one" aria-label={label} />
  );
}

describe("Select", () => {
  it("opens, moves and commits without a pointer", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    const trigger = screen.getByRole("combobox", { name: "Contract" });
    await user.tab();
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(await screen.findByRole("listbox")).toBeInTheDocument();

    await user.keyboard("{ArrowDown}{Enter}");
    expect(trigger).toHaveTextContent("To rent");
    // Focus comes back to the trigger, or the next Tab starts from nowhere.
    expect(trigger).toHaveFocus();
  });

  it("closes on Escape and leaves the value alone", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(
      <Select value="sale" onValueChange={onValueChange} options={OPTIONS} aria-label="Contract" />,
    );

    const trigger = screen.getByRole("combobox", { name: "Contract" });
    await user.tab();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("listbox")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(onValueChange).not.toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });

  it("shows the placeholder while nothing is chosen", () => {
    render(<Stateful />);
    expect(screen.getByRole("combobox", { name: "Contract" })).toHaveTextContent("Choose one");
  });

  it("says which option cannot be chosen", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{Enter}");
    await screen.findByRole("listbox");
    expect(screen.getByRole("option", { name: "At auction" })).toHaveAttribute("aria-disabled", "true");
  });

  it("takes its name and its wiring from a Field when it is inside one", () => {
    render(
      <Field label="Contract" error="Choose a contract type">
        <Select value="" onValueChange={vi.fn()} options={OPTIONS} placeholder="Choose one" />
      </Field>,
    );

    const trigger = screen.getByRole("combobox", { name: "Contract" });
    expect(trigger).toHaveAttribute("aria-invalid", "true");
    expect(trigger).toHaveAccessibleDescription("Choose a contract type");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Stateful />);
    await expectAccessible(container);
  });
});
