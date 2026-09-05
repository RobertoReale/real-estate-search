/**
 * Alternative views of one subject, one at a time.
 *
 * The keyboard behaviour is the reason this is not a row of buttons with an
 * `aria-selected`. A tab list is a *single* stop in the tab order: Tab moves
 * into the selected tab and then straight out to the panel, and the arrow keys
 * move between the tabs. Written by hand it comes out as N stops, so reaching
 * the content of a five-tab screen costs five presses of a key that is supposed
 * to move between regions. Radix implements the roving tabindex; nothing here
 * does.
 *
 * `activationMode="manual"` is a deliberate departure from the Radix default.
 * Automatic activation switches the panel as the arrow key moves, which is
 * pleasant when the panel is already in the browser and wrong here: two of the
 * three surfaces this will hold (Insights, the property detail) fetch when they
 * mount, so arrowing past a tab would fire a request for a panel the user never
 * asked to see.
 */
import { Tabs as TabsPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { cx, FOCUS_RING } from "./tone";

export interface TabItem {
  value: string;
  label: ReactNode;
  content: ReactNode;
  disabled?: boolean;
  /** The inventory id for this tab, per the control rule in `docs/conventions.md`. */
  "data-action"?: string;
}

export interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  items: readonly TabItem[];
  /** What the set of tabs is for, for a reader arriving at the list out of
   *  context — "Insights", not "Tabs". */
  label: string;
  className?: string;
}

export function Tabs({ value, onValueChange, items, label, className }: TabsProps) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange}
      activationMode="manual" className={cx("flex flex-col gap-4", className)}>
      <TabsPrimitive.List aria-label={label}
        className="flex items-center gap-1 overflow-x-auto rounded-control bg-sunken p-1">
        {items.map((item) => (
          <TabsPrimitive.Trigger key={item.value} value={item.value} disabled={item.disabled}
            data-action={item["data-action"]}
            className={cx(
              "whitespace-nowrap rounded-chip px-3 py-1.5 text-sm font-medium transition",
              "text-ink-muted hover:text-ink-body",
              "data-[state=active]:bg-control data-[state=active]:text-ink-strong",
              "data-[state=active]:shadow-e1",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              FOCUS_RING,
            )}>
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content key={item.value} value={item.value}
          className="focus-visible:outline-none">
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
