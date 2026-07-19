/** Turn a portal's raw floor code into a label a mixed audience can read.
 *
 * Immobiliare stores the floor as terse Italian abbreviations — "T" (terra),
 * "R" (rialzato), "S" (seminterrato), "PT" — that mean nothing to an
 * English-reading user staring at "floor R". Map the known codes to words, and
 * for a bare number keep the "floor N" reading. Anything already spelled out
 * ("attico", "piano terra") or shaped oddly ("R 6") passes through untouched, so
 * this never hides information — worst case it shows what it showed before.
 */
export function humanizeFloor(floor: string): string {
  const raw = (floor || "").trim();
  if (!raw) return "";
  const map: Record<string, string> = {
    t: "ground floor",
    pt: "ground floor",
    r: "raised ground floor",
    pr: "raised ground floor",
    s: "basement",
    sm: "basement",
  };
  const mapped = map[raw.toLowerCase()];
  if (mapped) return mapped;
  if (/^-?\d+$/.test(raw)) return `floor ${raw}`;
  return raw;
}
