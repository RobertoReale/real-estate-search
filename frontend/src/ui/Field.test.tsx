import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { expectAccessible } from "../test/axe";
import { Field } from "./Field";
import { Input } from "./Input";

describe("Field", () => {
  it("gives the control a name without the caller inventing an id", async () => {
    const user = userEvent.setup();
    render(<Field label="Municipality"><Input /></Field>);

    const input = screen.getByLabelText("Municipality");
    await user.tab();
    expect(input).toHaveFocus();
    await user.keyboard("Rome");
    expect(input).toHaveValue("Rome");
  });

  it("moves focus to the control when the label is clicked", async () => {
    const user = userEvent.setup();
    render(<Field label="Municipality"><Input /></Field>);

    await user.click(screen.getByText("Municipality"));
    expect(screen.getByLabelText("Municipality")).toHaveFocus();
  });

  it("describes the control with the hint, so it is read before the value is typed", () => {
    render(<Field label="Radius" hint="In kilometres from the centre"><Input /></Field>);

    expect(screen.getByLabelText("Radius"))
      .toHaveAccessibleDescription("In kilometres from the centre");
  });

  it("marks the control invalid because there is a message, not by a second prop", () => {
    const { rerender } = render(<Field label="Radius"><Input /></Field>);
    expect(screen.getByLabelText("Radius")).not.toHaveAttribute("aria-invalid");

    rerender(<Field label="Radius" error="Must be a number"><Input /></Field>);
    const input = screen.getByLabelText("Radius");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Must be a number");
    // Announced when it appears, for the user who has already moved on.
    expect(screen.getByRole("alert")).toHaveTextContent("Must be a number");
  });

  it("reads both the hint and the error when both are present", () => {
    render(
      <Field label="Radius" hint="In kilometres" error="Must be a number"><Input /></Field>,
    );
    expect(screen.getByLabelText("Radius"))
      .toHaveAccessibleDescription("In kilometres Must be a number");
  });

  it("says required to the browser as well as to the eye", () => {
    render(<Field label="Municipality" required><Input /></Field>);
    // The asterisk is in the label but `aria-hidden`, so the name a reader gets
    // is still the word; the `required` attribute is what carries the meaning.
    expect(screen.getByLabelText(/Municipality/)).toBeRequired();
    expect(screen.getByRole("textbox")).toHaveAccessibleName("Municipality");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(
      <Field label="Radius" hint="In kilometres" error="Must be a number"><Input /></Field>,
    );
    await expectAccessible(container);
  });
});
