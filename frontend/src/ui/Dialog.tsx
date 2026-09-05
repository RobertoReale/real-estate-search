/**
 * A window over the page, for something the user has to finish or abandon.
 *
 * The app already has two of these — settings and the property detail — and
 * each hand-rolled its own version of the same five obligations: trap the focus
 * inside, return it to whatever opened the dialog on close, close on Escape,
 * close on a click outside, and stop the page behind from scrolling. Both got
 * some of them. Neither returns focus, so closing settings with the keyboard
 * leaves the caret at the top of the document.
 *
 * All five come from Radix here, which is the entire argument for the
 * dependency: they are not hard to describe and they are very hard to get right
 * — the focus trap alone has to handle a dialog whose content changes while it
 * is open, an iframe, and a browser that fires `blur` in a different order.
 *
 * Two things this file decides rather than inherits:
 *
 * - **`closeLabel` is required.** It is the accessible name of the × in the
 *   corner, and a default would be an English word shipping into an Italian
 *   product every time somebody forgot it. Required, so the translation is not
 *   optional.
 * - **`z-[100]`, under the toasts at 200.** A write that fails while a dialog
 *   is open has to say so somewhere the user can read without closing the
 *   dialog and losing what they typed.
 */
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { IconButton } from "./IconButton";
import { useReturnFocus } from "./returnFocus";
import { cx } from "./tone";

const WIDTHS = { sm: "max-w-md", md: "max-w-2xl", lg: "max-w-4xl" } as const;

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Announced when the dialog opens, and the heading at the top of it. */
  title: ReactNode;
  /** One line on what this dialog is for. Omitted when the title says it all,
   *  in which case the dialog carries no `aria-describedby` at all rather than
   *  one pointing at a repeat of its own heading. */
  description?: ReactNode;
  /** The accessible name of the close button, translated by the caller. */
  closeLabel: string;
  size?: keyof typeof WIDTHS;
  /** Pinned to the bottom, outside the scrolling area: the confirm button of a
   *  long form must not be somewhere the user has to scroll to find. */
  footer?: ReactNode;
  children: ReactNode;
}

export function Dialog({
  open, onOpenChange, title, description, closeLabel, size = "md", footer, children,
}: DialogProps) {
  const onCloseAutoFocus = useReturnFocus(open);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-overlay backdrop-blur-sm" />
        <DialogPrimitive.Content
          onCloseAutoFocus={onCloseAutoFocus}
          className={cx(
            "fixed left-1/2 top-1/2 z-[100] flex max-h-[90vh] w-[calc(100vw-1.5rem)]",
            "-translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden",
            "rounded-surface border border-line bg-surface shadow-e3",
            WIDTHS[size],
          )}>
          <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
            <div className="min-w-0">
              <DialogPrimitive.Title className="text-lg font-semibold text-ink-strong">
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
