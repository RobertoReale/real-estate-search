/**
 * The same dialog, arriving from an edge.
 *
 * A phone has no room for a centred window: a modal that keeps a margin on
 * every side wastes a quarter of the screen and leaves the content in a column
 * narrow enough to break a price onto two lines. A sheet takes an edge and the
 * full measure of the other axis, which is why the filter rail (D.2) and the
 * property detail (D.3) are both sheets below `sm` and neither is a dialog with
 * different padding.
 *
 * Structurally it *is* a dialog — same Radix primitive, same focus trap, same
 * Escape — and it is a separate component rather than a `side` prop on `Dialog`
 * because the two have different shapes at the top: a sheet's header does not
 * scroll away, and a dialog's footer is pinned while a sheet's is inline. A
 * single component with a prop that changes both would be two components
 * sharing a name.
 */
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { IconButton } from "./IconButton";
import { useReturnFocus } from "./returnFocus";
import { cx } from "./tone";

const SIDES = {
  right: "inset-y-0 right-0 h-full w-[min(26rem,calc(100vw-2rem))] border-l",
  left: "inset-y-0 left-0 h-full w-[min(26rem,calc(100vw-2rem))] border-r",
  bottom: "inset-x-0 bottom-0 max-h-[85vh] w-full rounded-t-surface border-t",
} as const;

export interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  /** The accessible name of the close button, translated by the caller. */
  closeLabel: string;
  side?: keyof typeof SIDES;
  footer?: ReactNode;
  children: ReactNode;
}

export function Sheet({
  open, onOpenChange, title, description, closeLabel, side = "right", footer, children,
}: SheetProps) {
  const onCloseAutoFocus = useReturnFocus(open);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-overlay backdrop-blur-sm" />
        <DialogPrimitive.Content
          onCloseAutoFocus={onCloseAutoFocus}
          className={cx(
            "fixed z-[100] flex flex-col border-line bg-surface shadow-e3",
            SIDES[side],
          )}>
          <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-base font-semibold text-ink-strong">
                {title}
              </DialogPrimitive.Title>
              {description && (
                <DialogPrimitive.Description className="mt-0.5 text-xs text-ink-muted">
                  {description}
                </DialogPrimitive.Description>
              )}
            </div>
            <DialogPrimitive.Close asChild>
              <IconButton label={closeLabel} variant="ghost" size="sm">
                <svg aria-hidden="true" viewBox="0 0 12 12"
                  className="h-3 w-3 fill-none stroke-current stroke-2">
                  <path d="m2 2 8 8M10 2l-8 8" strokeLinecap="round" />
                </svg>
              </IconButton>
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
          {footer && (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line px-4 py-3">
              {footer}
            </div>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
