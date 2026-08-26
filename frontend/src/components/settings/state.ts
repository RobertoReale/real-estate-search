import { useState } from "react";
import { translateCurrent } from "../../i18n";
import type { Settings } from "../../types";

/** Which section a success/error message belongs to, so it can render there. */
export type SectionName = "telegram" | "email" | "global" | "data";

export interface Feedback {
  where: SectionName;
  ok: boolean;
  text: string;
}

/**
 * One section's slice of the settings form.
 *
 * State stays inside the section and is never lifted: the modal only ever asks
 * a section to re-seed itself from the server (`reset`) or to contribute its
 * half of the save (`payload`). Adding a field therefore touches one file —
 * which is the point of the split, since the single component this replaced
 * carried forty `useState` calls whose only relation was sharing a function
 * body, and every one of them had to be remembered in three separate places
 * (declaration, hydrate, payload) or the field silently stopped saving.
 */
export interface Section<T> {
  values: T;
  set: <K extends keyof T>(key: K, value: T[K]) => void;
  reset: (s: Settings) => void;
  payload: () => Partial<Settings>;
}

/**
 * Builds a `Section` from the three things that actually differ per section:
 * the fields' starting values, how to read them off a `Settings`, and how to
 * write them back. `initial` is needed because the hooks run before the first
 * `getSettings()` answers — the modal renders nothing until it does.
 */
export function useSectionState<T extends object>(
  initial: T,
  read: (s: Settings) => T,
  write: (values: T) => Partial<Settings>,
): Section<T> {
  const [values, setValues] = useState<T>(initial);
  return {
    values,
    set: (key, value) => setValues((v) => ({ ...v, [key]: value }) as T),
    reset: (s) => setValues(read(s)),
    payload: () => write(values),
  };
}

/**
 * What a section may ask of the modal around it. Sections own their fields;
 * saving, testing and the shared busy/feedback state stay with the shell, so a
 * section never has to know how the whole form is persisted.
 */
export interface SettingsShell {
  busy: SectionName | null;
  anyBusy: boolean;
  feedback: Feedback | null;
  setBusy: (where: SectionName | null) => void;
  setFeedback: (f: Feedback | null) => void;
  /** Re-seeds the form from the server, without saving first — for a section
   *  whose own action changed something server-side (a harvested cookie, a
   *  newly installed browser) and needs the reported state back. */
  reload: () => Promise<void>;
  /**
   * The test endpoints read the *saved* settings, not the form. Testing without
   * saving first silently exercised the previous credentials — the single most
   * confusing thing about this dialog — so every test button saves first.
   */
  saveAndTest: (
    where: SectionName,
    test: () => Promise<unknown>,
    describe: (result: unknown) => string,
  ) => Promise<void>;
}

/** Comma-separated free text (keywords, zones) to the list the API expects. */
export function splitList(text: string): string[] {
  return text.split(",").map((k) => k.trim()).filter(Boolean);
}

export function errorText(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  // Providers answer with protocol jargon; translate the two that a user can
  // actually act on, and pass everything else through untouched.
  if (/AUTHENTICATIONFAILED|Username and Password not accepted|535/i.test(raw)) {
    return translateCurrent("settings.errCredentials", { error: raw });
  }
  if (/timed out|timeout|Connection refused|getaddrinfo|Name or service not known/i.test(raw)) {
    return translateCurrent("settings.errNetwork", { error: raw });
  }
  return raw;
}
