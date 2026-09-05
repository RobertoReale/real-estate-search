/**
 * A panel anchored to the control that opened it, for detail the screen does
 * not have room to state.
 *
 * This is the shape rule 8 of the cycle asks for and the app currently has no
 * component for: *say it where the decision is made, and keep the detail one
 * click away rather than in the way.* Where a limit or a provenance note needs
 * more than a sentence — which portal a listing came from and when it was last
 * seen, why a zone was approximated — the sentence stays on the screen and the
 * rest goes in here.
 *
 * Not a tooltip. A tooltip is a label for something that has none and cannot
 * hold anything a user has to interact with; this holds paragraphs and links,
 * takes focus, and closes on Escape. Confusing the two is how a keyboard user
 * ends up with content they can see and cannot reach.
 */
import { Popover as PopoverPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { cx } from "./tone";

export interface PopoverProps {
  /** The control that opens it. Rendered as-is — pass a `Button` or an
   *  `IconButton` and it keeps its own styling, its own id and its own focus
   *  ring, and gains the `aria-expanded`/`aria-controls` wiring. */
  trigger: ReactNode;
  /** What the panel is about. Radix gives the panel `role="dialog"`, and a
   *  dialog with no accessible name is announced as "dialog" and nothing else —
   *  which is why this is required rather than optional. Translated by the
   *  caller, like every other string that reaches a user. */
  label: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  side?: "top" | "right" | "bottom" | "left";
  align?: "start" | "center" | "end";
  className?: string;
  children: ReactNode;
}

export function Popover({
  trigger, label, open, onOpenChange, side = "bottom", align = "center", className, children,
}: PopoverProps) {
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          aria-label={label}
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={12}
          className={cx(
            "z-[110] w-[min(20rem,calc(100vw-2rem))] rounded-card border border-line",
            "bg-raised p-3 text-sm text-ink-body shadow-e3",
            "focus-visible:outline-none",
            className,
          )}>
          {children}
          <PopoverPrimitive.Arrow className="fill-raised" width={12} height={6} />
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
