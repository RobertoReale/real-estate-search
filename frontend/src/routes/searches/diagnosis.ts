/** The diagnosis, turned from codes into something a person reads.
 *
 *  The backend answers in codes and never in sentences: `blocked`, `no_cookie`,
 *  `credit_cap`. That is deliberate — the wording belongs here, in the language
 *  its reader chose, next to every other string the app shows. The tables below
 *  are the whole translation, and they are exhaustive by type: a code the
 *  backend learns to send and this file does not know about fails `tsc`, which
 *  is the point of the closed sets on the API side.
 *
 *  A rung's name is not translated. `curl:chrome143` and `api:scrapfly` are what
 *  the harness calls them and what the logs and `docs/live-checks.md` call them,
 *  and inventing a second vocabulary for the same four transports would make the
 *  panel useless for the one thing it is for — saying which of them to go and
 *  fix. What is translated is the family, shown beside the exact name.
 */

import type { ChipTone } from "../../ui";
import type { TranslationKey } from "../../i18n";
import type { DiagnosisAdvice, DiagnosisOutcome, DiagnosisReason } from "../../types";

/** What the run as a whole means, and what the reader is being asked to do
 *  about it. `next` is empty for the one verdict that asks nothing. */
const ADVICE: Record<DiagnosisAdvice, {
  label: TranslationKey; next: TranslationKey | ""; tone: ChipTone;
}> = {
  works: { label: "diagnose.adviceWorks", next: "", tone: "positive" },
  no_results: {
    label: "diagnose.adviceNoResults", next: "diagnose.nextNoResults", tone: "neutral",
  },
  blocked: { label: "diagnose.adviceBlocked", next: "diagnose.nextBlocked", tone: "caution" },
  error: { label: "diagnose.adviceError", next: "diagnose.nextError", tone: "negative" },
  nothing_tried: {
    label: "diagnose.adviceNothing", next: "diagnose.nextNothing", tone: "neutral",
  },
};

export function adviceOf(advice: DiagnosisAdvice) {
  return ADVICE[advice];
}

/** Whether a rung answered, in one of three marks. A skipped rung gets neither
 *  tick nor cross: it was never asked, and scoring it as a failure would read as
 *  "the portal refused" for a transport that is merely switched off. */
export type Mark = "ok" | "bad" | "none";

const MARKS: Record<DiagnosisOutcome, Mark> = {
  ok: "ok",
  no_results: "ok",
  blocked: "bad",
  error: "bad",
  skipped: "none",
};

export function markOf(outcome: DiagnosisOutcome): Mark {
  return MARKS[outcome];
}

/** Why the rung ended as it did. `skipped` is the catch-all the backend falls
 *  back to when it cannot classify the harness's own words — the panel prints
 *  those words underneath, so an unclassified case is still legible. */
const REASONS: Record<DiagnosisReason, TranslationKey> = {
  ok: "diagnose.reasonOk",
  blocked: "diagnose.reasonBlocked",
  no_results: "diagnose.reasonNoResults",
  error: "diagnose.reasonError",
  no_cookie: "diagnose.reasonNoCookie",
  no_browser: "diagnose.reasonNoBrowser",
  no_api_key: "diagnose.reasonNoApiKey",
  no_official_key: "diagnose.reasonNoOfficialKey",
  paid_not_requested: "diagnose.reasonPaidNotRequested",
  budget: "diagnose.reasonBudget",
  streak: "diagnose.reasonStreak",
  request_cap: "diagnose.reasonRequestCap",
  credit_cap: "diagnose.reasonCreditCap",
  credit_floor: "diagnose.reasonCreditFloor",
  credit_unknown: "diagnose.reasonCreditUnknown",
  unsupported_search: "diagnose.reasonUnsupported",
  skipped: "diagnose.reasonSkipped",
};

export function reasonOf(reason: DiagnosisReason): TranslationKey {
  return REASONS[reason];
}

/** What family of transport a rung belongs to, from the name the harness gave
 *  it. Matched on the prefix, because the part after the colon is the profile or
 *  the provider — which is information, not a different transport. */
export function rungFamily(rung: string): TranslationKey {
  if (rung === "prepare") return "diagnose.rungPrepare";
  if (rung === "browser") return "diagnose.rungBrowser";
  if (rung === "official") return "diagnose.rungOfficial";
  if (rung.startsWith("curl+cookie")) return "diagnose.rungCookie";
  if (rung.startsWith("curl")) return "diagnose.rungDirect";
  if (rung.startsWith("api")) return "diagnose.rungApi";
  return "diagnose.rungOther";
}
