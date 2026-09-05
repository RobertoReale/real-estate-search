import { useCallback, useSyncExternalStore } from "react";

/**
 * Whether a CSS media query currently matches, as a value React can branch on.
 *
 * Almost everything responsive here is done in CSS, and should be: a Tailwind
 * `lg:` prefix costs nothing and cannot go out of step with the layout. This
 * exists for the one case CSS cannot serve — when the two shapes are not the
 * same markup shown differently but *different markup*. The filter rail is
 * inline on a desktop and a sheet on a phone; rendered both ways with one
 * hidden, every filter would exist twice, which means two elements answering to
 * "City", two entries in the tab order, and two of every `data-action` for the
 * inventory to trip over. One rendering, chosen here.
 *
 * `useSyncExternalStore` rather than an effect and a piece of state: the
 * subscription is the browser's, the snapshot is read at render time, and there
 * is no first paint at the wrong width to correct afterwards.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    // Server-rendered HTML has no viewport to measure. There is no SSR here,
    // but the snapshot is required and a false answer is the safe one: the
    // narrow layout is the one that fits everywhere.
    () => false,
  );
}

/** Tailwind's `lg` breakpoint, where the rail stops being a sheet. Spelled once
 *  so the hook and the stylesheet cannot disagree about where that is. */
export const DESKTOP_QUERY = "(min-width: 1024px)";
