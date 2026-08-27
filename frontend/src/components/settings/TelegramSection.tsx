import { useT } from "../../i18n";
import { api } from "../../services/api";
import type { Settings } from "../../types";
import { HelpSteps, Result, SecretStatus, SectionHeading } from "./controls";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  token: string;
  chatId: string;
  enabled: boolean;
  actions: boolean;
}

export function useTelegramSection(): Section<Values> {
  return useSectionState<Values>(
    { token: "", chatId: "", enabled: false, actions: true },
    (s) => ({
      // Write-only: the server never returns the token, so the field goes back
      // to its "already saved" placeholder rather than showing stale dots.
      token: "",
      chatId: s.telegram_chat_id,
      enabled: s.telegram_enabled,
      actions: s.telegram_actions_enabled ?? true,
    }),
    (v) => {
      const p: Partial<Settings> = {
        telegram_chat_id: v.chatId,
        telegram_enabled: v.enabled,
        telegram_actions_enabled: v.actions,
      };
      // An empty secret field means "keep the stored one", never "erase it".
      if (v.token.trim()) p.telegram_bot_token = v.token.trim();
      return p;
    },
  );
}

export function TelegramSection(
  { section, settings, shell }: { section: Section<Values>; settings: Settings; shell: SettingsShell },
) {
  const t = useT();
  const { values, set } = section;

  return (
    <>
      <SectionHeading first>{t("settings.telegramTitle")}</SectionHeading>
      <HelpSteps
        summary={t("settings.telegramHelp")}
        steps={[
          t("settings.tgStep1"),
          t("settings.tgStep2"),
          t("settings.tgStep3"),
          t("settings.tgStep4"),
          t("settings.tgStep5"),
          t("settings.tgStep6"),
        ]}
      />
      <div className="space-y-3">
        <div>
          <input className="input w-full" type="password"
            placeholder={t(settings.telegram_token_set ? "settings.tokenSaved" : "settings.tokenPlaceholder")}
            value={values.token} onChange={(e) => set("token", e.target.value)} />
          <div className="mt-1">
            <SecretStatus set={settings.telegram_token_set} dirty={!!values.token.trim()} />
          </div>
        </div>
        <input className="input w-full" placeholder={t("settings.chatIdPlaceholder")}
          value={values.chatId} onChange={(e) => set("chatId", e.target.value)} />
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={values.actions}
            onChange={(e) => set("actions", e.target.checked)} />
          {t("settings.telegramActions")}
        </label>
        <p className="text-xs opacity-70 -mt-2">{t("settings.telegramActionsHelp")}</p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={values.enabled}
              onChange={(e) => set("enabled", e.target.checked)} />
            {t("settings.enableTelegram")}
          </label>
          <button className="btn-ghost" disabled={shell.anyBusy}
            onClick={() => shell.saveAndTest("telegram", api.telegramTest,
              () => t("settings.telegramTestSent"))}>
            {shell.busy === "telegram" ? t("settings.sending") : t("settings.saveAndTest")}
          </button>
        </div>
        <Result feedback={shell.feedback} where="telegram" />
      </div>
    </>
  );
}
