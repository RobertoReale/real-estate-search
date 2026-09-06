/** What state a monitored search is in, as one value.
 *
 *  The list used to report health twice and in two registers: a coloured badge
 *  off to the right of the row, and — three lines away, under the URL and the
 *  criteria chips — a bare sentence from the last run ("the portal answered
 *  403"). Two readings of the same thing, neither of them complete, and the
 *  sentence was the one carrying the news. Worse, the badge and the on/off
 *  checkbox disagreed in the one case that matters most: a search switched off
 *  eleven days ago still showed "OK", because "OK" was what it said on its way
 *  out.
 *
 *  So health is a state here, derived once, and the run's own words go *with*
 *  it rather than beside it. Six states, and the precedence between them is the
 *  whole content of this file:
 *
 *  - `paused` wins over everything. A search that is off is not succeeding and
 *    not failing; it is not running, and that is the only true thing to say
 *    about it.
 *  - `failing` and `blocked` next, because they are the two the user has to act
 *    on, and they are different acts — an error is this app's problem, a block
 *    is the portal's.
 *  - `quiet` is deliberately not a warning. The portal answered and its answer
 *    was that nothing matches: a fact about the market, not a fault in the
 *    pipeline, and the distinction is the reason `no_results` exists as a
 *    separate status at all.
 *  - `working`, and `unrun` for a search saved but never yet swept.
 *
 *  Nothing here reads `notify_channels` — **invariant 21**: silencing a search
 *  and pausing it are different things, and a silenced search that is still
 *  running is healthy. Health answers "is it sweeping", never "will it tell me".
 */

import type { ChipTone } from "../../ui";
import type { TranslationKey } from "../../i18n";

export type HealthState =
  | "paused" | "failing" | "blocked" | "quiet" | "working" | "unrun";

/** Everything the state is derived from — a stored profile and a grouped one
 *  both satisfy it, which is what lets a merged row show the group's state and
 *  each portal's own without two code paths. */
export interface HealthInput {
  is_active: boolean;
  last_run_status: string;
  consecutive_failures: number;
  last_run_detail: string;
}

export interface Health {
  state: HealthState;
  label: TranslationKey;
  tone: ChipTone;
  /** How many sweeps in a row have failed. Rendered only past 1, where it stops
   *  being an incident and starts being a pattern. */
  streak: number;
  /** What the last run said, verbatim from the backend. Empty when it said
   *  nothing, which is the normal case for a search that simply worked. */
  detail: string;
}

const LABELS: Record<HealthState, { label: TranslationKey; tone: ChipTone }> = {
  paused: { label: "profiles.healthPaused", tone: "neutral" },
  failing: { label: "profiles.healthFailing", tone: "negative" },
  blocked: { label: "profiles.healthBlocked", tone: "caution" },
  quiet: { label: "profiles.healthQuiet", tone: "neutral" },
  working: { label: "profiles.healthWorking", tone: "positive" },
  unrun: { label: "profiles.healthUnrun", tone: "neutral" },
};

function stateOf(p: HealthInput): HealthState {
  if (!p.is_active) return "paused";
  if (p.last_run_status === "error") return "failing";
  if (p.last_run_status === "blocked") return "blocked";
  if (p.last_run_status === "no_results") return "quiet";
  if (p.last_run_status === "ok") return "working";
  return "unrun";
}

export function profileHealth(p: HealthInput): Health {
  const state = stateOf(p);
  return {
    state,
    ...LABELS[state],
    streak: Math.max(0, p.consecutive_failures || 0),
    detail: p.last_run_detail || "",
  };
}

/** Whether this state is one the user is being asked to do something about.
 *  `quiet` and `paused` are not: one is the market's answer and the other is
 *  the user's own decision, and colouring either of them as a problem is how a
 *  screen teaches its reader to stop reading colours. */
export function needsAttention(state: HealthState): boolean {
  return state === "failing" || state === "blocked";
}
