/**
 * A short label for a control whose meaning is not written on it.
 *
 * Two rules, and both are about the same failure — a tooltip is the easiest
 * place in a UI to put something only a mouse can find.
 *
 * **It never carries the only copy of anything.** No links, no buttons, no
 * sentence the user needs in order to decide. A tooltip is a hint; if the
 * content matters, it is a `Popover`, which takes focus and can be read with a
 * keyboard.
 *
 * **The trigger must be focusable.** Radix opens on focus as well as on hover,
 * so a tooltip on a `Button` works for a keyboard user for free — and a tooltip
 * on a `<span>` is invisible to them. Wrap a control, not a decoration.
 *
 * The `Provider` is inside rather than at the app root, which trades one thing
 * for another and it is worth naming which. What is lost is the shared delay: a
 * single provider knows that the user has already opened one tooltip, so the
 * next one appears immediately instead of after 700 ms. What is gained is a
 * component that cannot be mounted wrong — a Radix tooltip outside a provider
 * throws at render, and "add a provider you forgot" is the kind of error that
 * reaches a user because it only happens on the one screen nobody opened during
 * testing.
 */
import { Tooltip as TooltipPrimitive } from "radix-ui";
import type { ReactNode } from "react";

export interface TooltipProps {
  /** The words. Kept to a phrase — anything longer is a `Popover`. */
  label: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  /** Milliseconds of hover before it opens. Focus is always immediate. */
  delay?: number;
  children: ReactNode;
}

export function Tooltip({ label, side = "top", delay = 400, children }: TooltipProps) {
  return (
    <TooltipPrimitive.Provider delayDuration={delay}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            sideOffset={6}
            collisionPadding={8}
            className="z-[120] max-w-64 rounded-control border border-line bg-raised
              px-2.5 py-1.5 text-xs text-ink-body shadow-e2">
            {label}
            <TooltipPrimitive.Arrow className="fill-raised" width={10} height={5} />
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  );
}
