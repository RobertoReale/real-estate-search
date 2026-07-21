import { translateCurrent } from "../i18n";

/** Turn a portal's raw floor code into a label a mixed audience can read.
 *
 * Immobiliare stores the floor as terse Italian abbreviations — "T" (terra),
 * "R" (rialzato), "S" (seminterrato), "PT" — that mean nothing to an
 * English-reading user staring at "floor R". Map the known codes to words, and
 * for a bare number keep the "floor N" reading. Anything already spelled out
 * ("attico", "piano terra") or shaped oddly ("R 6") passes through untouched, so
 * this never hides information — worst case it shows what it showed before.
 *
 * The words themselves come from the dictionary, so an Italian UI gets "piano
 * terra" back rather than a translation of a translation.
 */
export function humanizeFloor(floor: string): string {
  const raw = (floor || "").trim();
  if (!raw) return "";
  const map = {
    t: "floor.ground",
    pt: "floor.ground",
    r: "floor.raised",
    pr: "floor.raised",
    s: "floor.basement",
    sm: "floor.basement",
  } as const;
  const key = map[raw.toLowerCase() as keyof typeof map];
  if (key) return translateCurrent(key);
  if (/^-?\d+$/.test(raw)) return translateCurrent("floor.numbered", { floor: raw });
  return raw;
}
