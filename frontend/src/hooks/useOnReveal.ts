import { useEffect, useRef, type RefObject } from "react";

/**
 * Calls `onReveal` when the element scrolls into view.
 *
 * The grid's "load the next page" sentinel. `rootMargin` pre-loads well before
 * the sentinel is reached, so scrolling feels seamless rather than paged.
 *
 * `onReveal` is read through a ref on purpose: it is a fresh closure on every
 * render, and depending on it would tear the observer down and rebuild it just
 * as often — which, on an element that is already in view, re-fires it each
 * time. The effect therefore turns on `enabled` alone.
 */
export function useOnReveal(
  ref: RefObject<HTMLElement | null>,
  enabled: boolean,
  onReveal: () => void,
): void {
  const latest = useRef(onReveal);
  latest.current = onReveal;

  useEffect(() => {
    if (!enabled) return;
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0]?.isIntersecting) latest.current(); },
      { rootMargin: "800px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, enabled]);
}
