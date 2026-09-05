import { useEffect, useState, type ReactNode } from "react";
import { useT } from "../i18n";
import { useSaveSettings, useSettingsForm } from "../queries/settings";
import { authToken } from "../services/api";
import type { Settings } from "../types";
import { Button, IconButton } from "../ui";
import { Close } from "../ui/icons";
import { AssistantSection, useAssistantSection } from "./settings/AssistantSection";
import { CommuteSection, useCommuteSection } from "./settings/CommuteSection";
import { EmailSection, useEmailSection } from "./settings/EmailSection";
import { MatchSection, useMatchSection } from "./settings/MatchSection";
import { ScanningSection, useScanningSection } from "./settings/ScanningSection";
import { ScrapingSection, useScrapingSection } from "./settings/ScrapingSection";
import { SystemSection, useSystemSection } from "./settings/SystemSection";
import { TelegramSection, useTelegramSection } from "./settings/TelegramSection";
import { errorText, useToasts } from "./Toast";
import { type Feedback, type SectionName, type SettingsShell } from "./settings/state";

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
    <div data-action="settings.close.backdrop" className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-overlay backdrop-blur-sm"
      onClick={onClose}>
      {/* dvh: `vh` on mobile spans behind the address bar, hiding the footer
          buttons ("Save settings") below the fold with no way to scroll to them */}
      <div data-action="settings.panel" className="glass rounded-2xl max-w-lg w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold">{t("settings.title")}</h2>
          <IconButton data-action="settings.close" label={t("common.close")} onClick={onClose}><Close size={16} /></IconButton>
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
  const toasts = useToasts();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState<SectionName | null>(null);
  // Re-read every time the dialog opens: a form seeded from a cached copy is a
  // form editing a snapshot, and the first save writes it back over whatever
  // else has changed since.
  const loaded = useSettingsForm();
  const saveSettings = useSaveSettings();
  // Why the failure is rendered instead of the form, even with a cached copy in
  // hand: the dialog is the one place the *saved* settings are authoritative,
  // and offering fields over a load that did not happen invites a save that
  // overwrites the ones on disk with a stale reading of them.
  const loadError = loaded.isError
    ? errorText(loaded.error)
    : "";

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

  // Seeds the form from whatever the query last delivered. `hydrate` closes
  // over the eight section hooks and so has a new identity every render, which
  // is why the effect turns on the answer rather than on the function.
  useEffect(() => {
    if (loaded.data) hydrate(loaded.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded.data]);

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
    // The server's answer is what masks the secrets back out, so it — not the
    // payload — is what the form is re-seeded from.
    hydrate(await saveSettings.mutateAsync(payload));
  }

  async function reload() {
    const { data } = await loaded.refetch();
    if (data) hydrate(data);
  }

  async function save() {
    setBusy("global");
    setFeedback(null);
    try {
      await persist();
      setFeedback({ where: "global", text: t("settings.saved") });
    } catch (e) {
      toasts.fail(e, { doing: t("toast.settingsSaveFailed"), retry: () => save() });
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
      // The test never ran, so this is the save's failure and says so — the
      // section's own settings are still only in the form.
      toasts.fail(e, { doing: t("toast.settingsSaveFailed") });
      setBusy(null);
      return;
    }
    try {
      setFeedback({ where, text: describe(await test()) });
    } catch (e) {
      toasts.fail(e, { retry: () => saveAndTest(where, test, describe) });
    } finally {
      setBusy(null);
    }
  }

  if (loadError) {
    return (
      <Shell onClose={onClose}>
        {/* In place of the form rather than beside it: this is what the dialog
            has to show when it has nothing to show, and it is the one screen
            whose own failure must not be reported anywhere the user has to
            close the dialog to read. */}
        <p role="status" className="text-sm t-muted">
          {t("settings.loadFailed", { error: loadError })}
        </p>
        <div className="flex justify-end gap-2 mt-6">
          <Button data-action="settings.loadError.close" onClick={onClose}>{t("common.close")}</Button>
          <Button data-action="settings.loadError.retry" variant="solid" tone="accent"
            onClick={() => void loaded.refetch()}>
            {t("common.retry")}
          </Button>
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
        <Button data-action="settings.footer.close" onClick={onClose}>{t("common.close")}</Button>
        <Button data-action="settings.save" variant="solid" tone="accent" onClick={save}
          disabled={shell.anyBusy}>
          {busy === "global" ? t("common.saving") : t("settings.save")}
        </Button>
      </div>
    </Shell>
  );
}
