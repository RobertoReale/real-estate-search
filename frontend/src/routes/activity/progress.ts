/** Turning what the scanner reports into what may be shown.
 *
 *  Two decisions live here rather than in the components, because both are
 *  rules rather than markup and a rule in a `.tsx` is a rule nobody tests.
 *
 *  The first is the one this whole screen is constrained by: **a proportion may
 *  only be drawn where a portal stated a total.** `ScanProgressOut.total_pages`
 *  is `null` far more often than not — Immobiliare declares a page count and
 *  Idealista frequently does not — so the default answer is "no bar", and
 *  `pageProportion` is the single place that answer is decided.
 *
 *  The second is that every word on the screen comes from a translation key.
 *  The backend's `detail` and `stopped_because` are English prose written for
 *  whoever reads the log; the phase and the outcome are closed vocabularies,
 *  and mapping them here is what lets the screen speak Italian.
 */
import type { TranslationKey } from "../../i18n";
import type { ChipTone } from "../../ui";
import type { ScanProgress } from "../../types";

/** The scanner's phases, as something a person reads. Anything unrecognised
 *  falls back to a vague "scanning" rather than to the backend's English
 *  `detail`: a phase name added to a newer backend should reach an older
 *  dashboard as imprecise, never as untranslated. */
const PHASE_LABEL: Record<string, TranslationKey> = {
  starting: "activity.phaseStarting",
  locating: "activity.phaseLocating",
  fetching: "activity.phaseFetching",
  waiting: "activity.phaseWaiting",
  saving: "activity.phaseSaving",
};

export function phaseLabel(phase: string): TranslationKey {
  return PHASE_LABEL[phase] ?? "activity.phaseScanning";
}

/** How a search ended, in G.5's four words. */
const OUTCOME: Record<string, { label: TranslationKey; tone: ChipTone }> = {
  ok: { label: "activity.outcomeOk", tone: "positive" },
  no_results: { label: "activity.outcomeNoResults", tone: "neutral" },
  blocked: { label: "activity.outcomeBlocked", tone: "caution" },
  error: { label: "activity.outcomeError", tone: "negative" },
};

export function outcomeLabel(outcome: string): { label: TranslationKey; tone: ChipTone } {
  return OUTCOME[outcome] ?? { label: "activity.outcomeUnknown", tone: "neutral" };
}

/** Whether the reason a search stopped is worth a line of its own.
 *
 *  It is the backend's own sentence, so it is spent where `ProfileHealth`
 *  already spends `last_run_detail`: on the runs that did not simply work. On a
 *  successful one the counts have already said everything, and an extra clause
 *  under every row is how a list stops being scannable. */
export function worthExplaining(outcome: string): boolean {
  return outcome !== "ok";
}

export interface Proportion {
  readonly done: number;
  readonly total: number;
}

/**
 * The pages as a fraction, or `null` if there is no honest fraction to draw.
 *
 * `null` is the common case and the safe one — it means the caller shows a
 * count that rises. A total is only believed when the portal gave a positive
 * one, and `done` is clamped to it: a portal that declares eight pages and
 * serves nine would otherwise produce a bar past its own end, which is the same
 * lie in the opposite direction.
 */
export function pageProportion(progress: ScanProgress | null | undefined): Proportion | null {
  const total = progress?.total_pages;
  if (!progress || typeof total !== "number" || total <= 0) return null;
  return { done: Math.min(Math.max(progress.page, 0), total), total };
}
