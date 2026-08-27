import { useEffect, useState } from "react";
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

  useEffect(() => {
    api.getSettings().then(hydrate);
  }, []);

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

  if (!settings) return null;

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      {/* dvh: `vh` on mobile spans behind the address bar, hiding the footer
          buttons ("Save settings") below the fold with no way to scroll to them */}
      <div className="glass rounded-2xl max-w-lg w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold">{t("settings.title")}</h2>
          <button className="btn-ghost" aria-label={t("common.close")} onClick={onClose}>✕</button>
        </div>

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
          <button className="btn-ghost" onClick={onClose}>{t("common.close")}</button>
          <button className="btn-primary" onClick={save} disabled={shell.anyBusy}>
            {busy === "global" ? t("common.saving") : t("settings.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
