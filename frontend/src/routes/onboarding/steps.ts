/** The guided first run, as a state machine — apart from anything that draws it.
 *
 *  Three steps, in one order: what this is, the first search, the first scan.
 *  Two rules decide which of them a user is looking at, and both are here rather
 *  than inside the component, because both are the kind of thing that is easy to
 *  get right once and then break in a re-render:
 *
 *  - **a step is never reached before it means anything.** "Run your first scan"
 *    with nothing to scan is a button that fails for a reason the user did not
 *    cause, so the third step is unreachable until a search exists. The guide
 *    does not enforce that with a disabled control it also has to explain — it
 *    clamps the step, which is one rule instead of one per control.
 *  - **leaving is remembered.** The bare address opens the guide while there is
 *    nothing else to show, and a user who has said "not now" must not meet it
 *    again on the next visit. The flag is per device, like the theme and the
 *    seen-before threshold, and it is written the moment the guide is left
 *    rather than when it is finished: skipping is a decision too.
 */

export const STEPS = ["what", "search", "scan"] as const;
export type Step = (typeof STEPS)[number];

/** Per device, in localStorage: this is a fact about this browser rather than
 *  about the data, and a second machine deserves the guide of its own accord. */
const DISMISSED_KEY = "firstRunGuideDismissed";

export function guideDismissed(): boolean {
  return localStorage.getItem(DISMISSED_KEY) === "1";
}

export function dismissGuide(): void {
  localStorage.setItem(DISMISSED_KEY, "1");
}

/** The furthest step that means anything yet. */
export function furthestStep(hasSearch: boolean): Step {
  return hasSearch ? "scan" : "search";
}

/** The step actually shown for the one asked for. */
export function clampStep(chosen: Step, hasSearch: boolean): Step {
  const limit = STEPS.indexOf(furthestStep(hasSearch));
  return STEPS[Math.min(STEPS.indexOf(chosen), limit)];
}

/** The next step, or this one when there is no next. The caller renders a
 *  finish control at the end rather than a Next that goes nowhere, so this
 *  saturating rather than nullable keeps the arithmetic out of the component. */
export function stepAfter(step: Step): Step {
  return STEPS[Math.min(STEPS.indexOf(step) + 1, STEPS.length - 1)];
}

/** The previous step, or `null` on the first one. */
export function stepBefore(step: Step): Step | null {
  const index = STEPS.indexOf(step);
  return index > 0 ? STEPS[index - 1] : null;
}

/** Whether the bare address should open the guide rather than the listings.
 *
 *  Only for a database that has never held a search: once one exists the app
 *  has something to show, and the default destination is where it is shown. */
export function shouldGuide(hasSearch: boolean): boolean {
  return !hasSearch && !guideDismissed();
}
