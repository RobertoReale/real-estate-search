import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Checkbox } from "./Checkbox";
import { Field } from "./Field";

/** The controlled wrapper every caller writes anyway. */
function Stateful({ initial = false, label = "Only new listings" }: {
  initial?: boolean | "indeterminate";
  label?: string;
}) {
  const [checked, setChecked] = useState<boolean | "indeterminate">(initial);
  return <Checkbox checked={checked} onCheckedChange={setChecked} label={label} />;
}

describe("Checkbox", () => {
  it("toggles with Space, the key the platform control answers to", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    const box = screen.getByRole("checkbox", { name: "Only new listings" });
    await user.tab();
    expect(box).toHaveFocus();

    await user.keyboard(" ");
    expect(box).toBeChecked();
    await user.keyboard(" ");
    expect(box).not.toBeChecked();
  });

  it("is toggled by its label, which is a target a fingertip can hit", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.click(screen.getByText("Only new listings"));
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("says mixed when some of the selection is checked", async () => {
    const user = userEvent.setup();
    const onCheckedChange = vi.fn();
    render(
      <Checkbox checked="indeterminate" onCheckedChange={onCheckedChange} label="Select all" />,
    );

    // The reason this is not a native input: `indeterminate` is a DOM property
    // with no attribute, so a native checkbox can only be made mixed by reaching
    // for the element after render. Here it is the value.
    const box = screen.getByRole("checkbox", { name: "Select all" });
    expect(box).toHaveAttribute("aria-checked", "mixed");

    await user.tab();
    await user.keyboard(" ");
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });

  it("is skipped by Tab when disabled", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Checkbox checked={false} onCheckedChange={vi.fn()} label="Off limits" disabled />
        <Checkbox checked={false} onCheckedChange={vi.fn()} label="After" />
      </>,
    );

    await user.tab();
    expect(screen.getByRole("checkbox", { name: "After" })).toHaveFocus();
  });

  it("takes its name and its wiring from a Field when it is inside one", () => {
    render(
      <Field label="Availability" hint="Checked at most once an hour">
        <Checkbox checked={false} onCheckedChange={vi.fn()} />
      </Field>,
    );

    const box = screen.getByRole("checkbox", { name: "Availability" });
    expect(box).toHaveAccessibleDescription("Checked at most once an hour");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Stateful initial />);
    await expectAccessible(container);
  });
});
