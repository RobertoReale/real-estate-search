import { useEffect, useState } from "react";

/**
 * The value as it was `delayMs` ago, if it has stopped changing since.
 *
 * The filter bar produces a new filter set on every keystroke, and each distinct
 * set is a distinct query — so without this, typing "Milano" is six requests for
 * six answers, five of which nobody will ever see. Debouncing the *key* rather
 * than the request is what keeps that from happening at all: the query never
 * exists, instead of existing and being thrown away.
 *
 * It is not a race guard and never was. Which answer reaches the screen is
 * decided by which key is being watched (see `queries/properties.ts`); this only
 * decides how many are asked for.
 */
export function useDebounced<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
