/** Something this app cannot do, said where it bites.
 *
 *  The rule this exists to hold: **a limit is stated where it bites, not on a
 *  page nobody opens.** A page cap the user meets as "why are there only 250
 *  listings" is a bug; the same cap printed beside the count is a fact. So every
 *  one of them is a sentence on the screen it qualifies, and `docs/limits.md` is
 *  the checklist of which screen that is.
 *
 *  Two tones, and the split is the whole design:
 *
 *  - `note` is the default and the ordinary case. Most of these limits are
 *    fine — a zone matched by name, a pin on a district centre, a walk measured
 *    on the road network. They are printed quietly, next to the number they
 *    qualify, in the same weight as the rest of the small print.
 *  - `incomplete` is reserved for the two that mean *the answer in front of you
 *    is not the whole answer*: a portal that blocked the request, and a search
 *    that stopped at the page limit with listings still to collect.
 *
 *  Rendering twelve yellow triangles would teach the user to skip past the one
 *  that matters, which is exactly the case `incomplete` is being saved for.
 *  Nothing here is interactive: a limit is a statement, not a control, so it
 *  carries no action and asks for no decision.
 *
 *  `id` names the limit rather than the place — the same limit stated on two
 *  screens carries the same id — and it is also what the browser suite asserts
 *  on, which is how the numbers below are checked against the API's answer
 *  rather than against a translation string.
 */
import type { ReactNode } from "react";
import { cx } from "../ui";

export type LimitTone = "note" | "incomplete";

export interface LimitProps {
  /** Which limit this is, in dot notation (`scan.pageCap`, `map.zoneCentroid`). */
  id: string;
  tone?: LimitTone;
  className?: string;
  children: ReactNode;
}

const TONES: Record<LimitTone, string> = {
  note: "t-muted",
  incomplete: "text-caution-ink",
};

export function Limit({ id, tone = "note", className, children }: LimitProps) {
  return (
    <p data-limit={id} className={cx("text-xs", TONES[tone], className)}>
      {children}
    </p>
  );
}

/** The same statement inline, for a place that already has a line of small
 *  print to hang it on rather than room for one of its own — a card's marker
 *  strip, a badge. Same ids, same tones, same rule. */
export function LimitInline({ id, tone = "note", className, children }: LimitProps) {
  return (
    <span data-limit={id} className={cx(TONES[tone], className)}>
      {children}
    </span>
  );
}
