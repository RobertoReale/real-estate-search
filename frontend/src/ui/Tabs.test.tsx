import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { expectAccessible } from "../test/axe";
import { Tabs, type TabItem } from "./Tabs";

const ITEMS: TabItem[] = [
  { value: "prices", label: "Prices", content: <p>The price panel.</p> },
  { value: "supply", label: "Supply", content: <p>The supply panel.</p> },
  { value: "zones", label: "Zones", content: <p>The zone panel.</p> },
];

function Stateful({ onValueChange }: { onValueChange?: (value: string) => void }) {
  const [value, setValue] = useState("prices");
  return (
    <Tabs value={value} label="Insights" items={ITEMS}
      onValueChange={(next) => { setValue(next); onValueChange?.(next); }} />
  );
}

describe("Tabs", () => {
  it("is one stop in the tab order, with the arrows moving between the tabs", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    expect(screen.getByRole("tab", { name: "Prices" })).toHaveFocus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Supply" })).toHaveFocus();

    // The second Tab leaves the list entirely rather than visiting tab three.
    await user.tab();
    expect(screen.getByRole("tab", { name: "Zones" })).not.toHaveFocus();
  });

  it("does not switch the panel until the user says so", async () => {
    const user = userEvent.setup();
    const onValueChange = vi.fn();
    render(<Stateful onValueChange={onValueChange} />);

    await user.tab();
    await user.keyboard("{ArrowRight}");
    // Manual activation, on purpose: two of the panels fetch when they mount, so
    // arrowing past one must not fire a request for a panel nobody asked for.
    expect(onValueChange).not.toHaveBeenCalled();
    expect(screen.getByText("The price panel.")).toBeInTheDocument();

    await user.keyboard("{Enter}");
    expect(onValueChange).toHaveBeenCalledWith("supply");
    expect(screen.getByText("The supply panel.")).toBeInTheDocument();
  });

  it("wraps from the last tab to the first", async () => {
    const user = userEvent.setup();
    render(<Stateful />);

    await user.tab();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Zones" })).toHaveFocus();
  });

  it("names the set for a reader arriving at it out of context", () => {
    render(<Stateful />);
    expect(screen.getByRole("tablist")).toHaveAccessibleName("Insights");
  });

  it("shows one panel, wired to the tab that selected it", () => {
    render(<Stateful />);

    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveTextContent("The price panel.");
    expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
    expect(screen.getByRole("tab", { name: "Prices" })).toHaveAttribute("aria-selected", "true");
  });

  it("has no accessibility violations", async () => {
    const { container } = render(<Stateful />);
    await expectAccessible(container);
  });
});
