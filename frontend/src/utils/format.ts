import { translateCurrent } from "../i18n";
import type { CommuteMode } from "../types";
import { ByBike, ByCar, type Icon, OnFoot } from "../ui/icons";

/** The backend sends OSRM's raw metres and seconds, so the rounding lives here
 *  — one place, shared by the card and the modal, rather than two `toFixed`
 *  calls that would drift the moment one of them gained an hours case. */
export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return translateCurrent("commute.minutes", { count: minutes });
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0
    ? translateCurrent("commute.hours", { count: hours })
    : translateCurrent("commute.hoursMinutes", { hours, minutes: rest });
}

export function formatDistance(metres: number): string {
  return metres < 1000
    ? translateCurrent("commute.metres", { count: Math.round(metres) })
    : translateCurrent("commute.kilometres", { count: (metres / 1000).toFixed(1) });
}

/** "2025/2" → "2nd half 2025". The backend stores an OMI semester the way the
 *  Agenzia writes it, which is not a date anyone reads at a glance.
 *
 *  A string that is not a semester is returned as it stands: it is still the
 *  label the import recorded, and dropping it would leave the figure undated —
 *  the one thing these numbers must never be. */
export function formatSemester(semester: string): string {
  const match = /^\s*(\d{4})\s*\/\s*(\d+)\s*$/.exec(semester || "");
  if (!match) return semester || "";
  const [, year, half] = match;
  if (half === "1") return translateCurrent("benchmark.semesterFirst", { year });
  if (half === "2") return translateCurrent("benchmark.semesterSecond", { year });
  return semester;
}

/** How the leg is travelled, at a glance. Kept out of the dictionary on
 *  purpose: a drawing is the same in every language. The map lives here rather
 *  than in `ui/icons.tsx` because `CommuteMode` is a fact about this product
 *  and the icon set is not allowed to know any. */
export const COMMUTE_ICONS: Record<CommuteMode, Icon> = {
  car: ByCar,
  foot: OnFoot,
  bike: ByBike,
};

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
