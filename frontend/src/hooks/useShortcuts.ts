/** Single-key shortcuts, registered on the window and scoped by the caller.
 *
 *  Every shortcut in the app goes through here, for two reasons. The first is
 *  that the rules a bare letter has to obey are the same everywhere and are easy
 *  to forget one of: a modifier means the key belongs to the browser, a field
 *  under the focus means the user is typing rather than commanding, and a
 *  half-composed IME sequence is neither. The second is scoping — `f` may mean
 *  "favourite" on the grid and nothing at all with a dialog open over it, and
 *  the honest way to express that is a screen registering its keys and
 *  unregistering them when it stops being the screen.
 *
 *  A `run` that returns `false` **declines** the key: the shortcut was the right
 *  one but there was nothing to do with it, so the default is left alone. That
 *  is what keeps `j` at the end of the list scrolling the page instead of being
 *  swallowed by a handler with no next property to go to.
 */
import { useEffect, useRef } from "react";

export interface Shortcut {
  /** The `KeyboardEvent.key` values that trigger it. */
  readonly keys: readonly string[];
  /** What it does. Return `false` to decline the key and leave the default. */
  readonly run: () => boolean | void;
  /** Fires even when the focus is in a field. Escape is the only key that
   *  legitimately wants this — the rest would be typing. */
  readonly whileTyping?: true;
}

/** Whether the event landed in something the user is typing into. */
export function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof Element
    && target.closest("input, textarea, select, [contenteditable='true']") !== null
  );
}

/**
 * Binds `shortcuts` while `enabled`, first match wins.
 *
 * The list is read through a ref, so handlers may close over whatever they like
 * without the listener being torn down and rebuilt on every render — only
 * `enabled` does that, which is the one change that must reach the window.
 */
export function useShortcuts(shortcuts: readonly Shortcut[], enabled = true): void {
  const latest = useRef(shortcuts);
  useEffect(() => {
    latest.current = shortcuts;
  });

  useEffect(() => {
    if (!enabled) return;
    function onKey(event: KeyboardEvent) {
      // A modified key is the browser's or the OS's, and a key pressed mid-IME
      // composition is a syllable being assembled, not a command.
      if (event.altKey || event.ctrlKey || event.metaKey || event.isComposing) return;
      const typing = isTyping(event.target);
      for (const shortcut of latest.current) {
        if (!shortcut.keys.includes(event.key)) continue;
        if (typing && !shortcut.whileTyping) continue;
        if (shortcut.run() === false) continue;
        event.preventDefault();
        return;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [enabled]);
}
