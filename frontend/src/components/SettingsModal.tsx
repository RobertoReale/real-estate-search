import { useEffect, useState, type ReactNode } from "react";
import { useT } from "../i18n";
import { api, authToken } from "../services/api";
import type { Settings } from "../types";
import { AssistantSection, useAssistantSection } from "./settings/AssistantSection";
import { CommuteSection, useCommuteSection } from "./settings/CommuteSection";
import { EmailSection, useEmailSection } from "./settings/EmailSection";
import { MatchSection, useMatchSection } from "./settings/MatchSection";
import { ScanningSection, useScanningSection } from "./settings/ScanningSection";
import { ScrapingSection, useScrapingSection } from "./settings/ScrapingSection";
import { SystemSection, useSystemSection } from "./settings/SystemSection";
import { TelegramSection, useTelegramSection } from "./settings/TelegramSection";
import { errorText, type Feedback, type SectionName, type SettingsShell } from "./settings/state";

interface Props {
  onClose: () => void;
}

/** The dialog frame — overlay, panel, title and close button — shared by the
 *  loading, failed and loaded states. Module-level rather than nested in
 *  `SettingsModal`: a component declared inside another is a new type on every
 *  render, which would remount the whole form (and drop focus) per keystroke. */
function Shell({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  const t = useT();
  return (
    <div data-action="settings.close.backdrop" className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      {/* dvh: `vh` on mobile spans behind the address bar, hiding the footer
          buttons ("Save settings") below the fold with no way to scroll to them */}
      <div data-action="settings.panel" className="glass rounded-2xl max-w-lg w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold">{t("settings.title")}</h2>
          <button data-action="settings.close" className="btn-ghost" aria-label={t("common.close")} onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

/**
 * The dialog is only the shell: it loads the settings once, hands each section
 * its slice, and owns the three things that genuinely are shared — the busy
 * marker, the feedback line and the save itself. Every field lives in the
 * section that renders it (`components/settings/`), so a new setting is one
 * file's problem rather than three edits spread across a thousand lines.
 */
export default function SettingsModal({ onClose }: Props) {
  const t = useT();
  const [settings, setSettings] = useState<Settings | null>(null);
  // Why the load needs its own error state: the dialog cannot render a single
  // field until `getSettings` answers, so a backend that is down or 500s used
  // to leave `settings` null for ever — the gear button opened nothing at all,
  // with not even a close button, and the rejection went unhandled.
  const [loadError, setLoadError] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState<SectionName | null>(null);

  const telegram = useTelegramSection();
  const email = useEmailSection();
  const scanning = useScanningSection();
  const match = useMatchSection();
  const commute = useCommuteSection();
  const assistant = useAssistantSection();
  const scraping = useScrapingSection();
  const system = useSystemSection();

  // Only the two halves of the contract the shell actually uses: re-seed
  // yourself from the server, and hand over your part of the save.
  const sections: { reset: (s: Settings) => void; payload: () => Partial<Settings> }[] =
    [telegram, email, scanning, match, commute, assistant, scraping, system];

  // Bumped by the retry button. `hydrate` closes over the eight section hooks
  // and so has a new identity every render; a counter is what re-runs the load
  // without making the effect depend on it.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoadError("");
    api.getSettings()
      .then((s) => { if (!cancelled) hydrate(s); })
      .catch((e) => { if (!cancelled) setLoadError(errorText(e)); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  function hydrate(s: Settings) {
    setSettings(s);
    for (const section of sections) section.reset(s);
  }

  /** Persists the form and refreshes local state from the server's answer. */
  async function persist() {
    const payload = sections.reduce<Partial<Settings>>(
      (acc, section) => ({ ...acc, ...section.payload() }), {});
    // Keep this browser's stored token in step with the field, so enabling auth
    // does not lock out the very next request (and clearing it removes the
    // token). It has to happen here rather than in the section, because it must
    // land before the request that the new token will be checked against.
    const token = system.values.apiToken.trim();
    if (token) authToken.set(token);
    else authToken.clear();
    hydrate(await api.updateSettings(payload));
  }

  async function reload() {
    hydrate(await api.getSettings());
  }

  async function save() {
    setBusy("global");
    setFeedback(null);
    try {
      await persist();
      setFeedback({ where: "global", ok: true, text: t("settings.saved") });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  async function saveAndTest(
    where: SectionName,
    test: () => Promise<unknown>,
    describe: (result: unknown) => string,
  ) {
    setBusy(where);
    setFeedback(null);
    try {
      await persist();
    } catch (e) {
      setFeedback({ where, ok: false, text: t("settings.saveFailed", { error: errorText(e) }) });
      setBusy(null);
      return;
    }
    try {
      setFeedback({ where, ok: true, text: describe(await test()) });
    } catch (e) {
      setFeedback({ where, ok: false, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  if (loadError) {
    return (
      <Shell onClose={onClose}>
        <p role="status"
          className="text-sm rounded-lg px-3 py-2 bg-rose-500/10 text-rose-700 dark:text-rose-300">
          ❌ {t("settings.loadFailed", { error: loadError })}
        </p>
        <div className="flex justify-end gap-2 mt-6">
          <button data-action="settings.loadError.close" className="btn-ghost" onClick={onClose}>{t("common.close")}</button>
          <button data-action="settings.loadError.retry" className="btn-primary" onClick={() => setAttempt((n) => n + 1)}>
            {t("common.retry")}
          </button>
        </div>
      </Shell>
    );
  }

  if (!settings) {
    return (
      <Shell onClose={onClose}>
        <p className="text-sm t-muted">{t("common.loading")}</p>
      </Shell>
    );
  }

  const shell: SettingsShell = {
    busy,
    anyBusy: busy !== null,
    feedback,
    setBusy,
    setFeedback,
    reload,
    saveAndTest,
  };

  return (
    <Shell onClose={onClose}>
      <p className="text-xs t-dim mb-5">{t("settings.testNote")}</p>

      <TelegramSection section={telegram} settings={settings} shell={shell} />
      <EmailSection section={email} settings={settings} shell={shell} />
      <ScanningSection section={scanning} />
      <MatchSection section={match} />
      <CommuteSection section={commute} settings={settings} shell={shell} />
      <AssistantSection section={assistant} settings={settings} />
      <ScrapingSection section={scraping} settings={settings} shell={shell} />
      <SystemSection section={system} settings={settings} shell={shell} />

      <div className="flex justify-end gap-2 mt-6">
        <button data-action="settings.footer.close" className="btn-ghost" onClick={onClose}>{t("common.close")}</button>
        <button data-action="settings.save" className="btn-primary" onClick={save} disabled={shell.anyBusy}>
          {busy === "global" ? t("common.saving") : t("settings.save")}
        </button>
      </div>
    </Shell>
  );
}
