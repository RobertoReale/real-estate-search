import type { ReactNode } from "react";
import { formatDate, formatDateTime, useT } from "../../i18n";
import type { Feedback, SectionName } from "./state";

/** The standard section title. `first` drops the top margin, since the opening
 *  section sits directly under the dialog's intro line. */
export function SectionHeading({ first, children }: { first?: boolean; children: ReactNode }) {
  return (
    <h3 className={`font-semibold text-sm uppercase t-muted mb-2 ${first ? "" : "mt-6"}`}>
      {children}
    </h3>
  );
}

export function HelpSteps({ summary, steps }: { summary: string; steps: ReactNode[] }) {
  return (
    <details className="text-xs t-muted mb-3 rounded-lg panel">
      <summary className="cursor-pointer px-3 py-2 select-none hover:text-ink-strong transition">
        {summary}
      </summary>
      <ol className="px-3 pb-3 pt-1 space-y-1.5 list-decimal list-inside">
        {steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
    </details>
  );
}

export function Link({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer"
      className="underline underline-offset-2 hover:text-ink-strong">
      {children}
    </a>
  );
}

/** Whether a write-only secret (API key, token, password, cookie) is currently
 *  stored on the server. These inputs are masked and the backend never returns
 *  the value, so the only previous cue was faint placeholder text — this makes
 *  the state unmistakable. `dirty` = the field holds unsaved input that will
 *  replace what is stored; `since` (when known) adds the save date. */
export function SecretStatus({ set, since, dirty }: { set?: boolean; since?: string; dirty?: boolean }) {
  const t = useT();
  if (dirty) {
    return (
      <span className="inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full chip-caution">
        {t("settings.secretDirty")}
      </span>
    );
  }
  if (set) {
    return (
      <span title={since
        ? t("settings.secretLastSaved", { date: formatDateTime(since) })
        : t("settings.secretSavedTitle")}
        className="inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full chip-positive">
        {since
          ? t("settings.secretSavedOn", { date: formatDate(since) })
          : t("settings.secretSaved")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-2xs font-medium px-2 py-0.5 rounded-full chip-neutral">
      {t("settings.secretNotSet")}
    </span>
  );
}

/** Renders the shared feedback line, but only for the section that raised it.
 *  Success only: what a section reports here is the result of an action whose
 *  controls are right above it, and a failure has an instruction attached that
 *  belongs in the toast rather than in a line of prose. */
export function Result({ feedback, where }: { feedback: Feedback | null; where: SectionName }) {
  if (!feedback || feedback.where !== where) return null;
  return (
    <p role="status"
      className="text-sm mt-3 rounded-lg px-3 py-2
        bg-positive-tint text-positive-ink">
      ✅ {feedback.text}
    </p>
  );
}
