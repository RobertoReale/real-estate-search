/**
 * Where the keyboard goes when an overlay closes.
 *
 * Radix restores focus to its own `Dialog.Trigger`, and `Dialog` and `Sheet`
 * here have none: they are driven by `open`, because the thing that opens a
 * confirmation is as often a row action or a keyboard shortcut as it is a button
 * sitting next to it. With no trigger to go back to, Radix's close handler
 * focuses nothing and the keyboard lands on `<body>` — which for a user
 * navigating by Tab means starting again from the top of the page, every time
 * they dismiss anything.
 *
 * So this remembers what was focused at the moment the overlay opened and puts
 * the keyboard back there. `isConnected` is the guard that matters: the control
 * that opened the dialog is quite often the one the dialog removes — "delete
 * this search" being the obvious case — and focusing a detached node silently
 * does nothing at all. When it has gone, Radix's own fallback is left to run.
 */
import { useCallback, useEffect, useRef } from "react";

export function useReturnFocus(open: boolean) {
  const opener = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) opener.current = document.activeElement as HTMLElement | null;
  }, [open]);

  return useCallback((event: Event) => {
    const previous = opener.current;
    if (previous?.isConnected) {
      event.preventDefault();
      previous.focus();
    }
  }, []);
}
