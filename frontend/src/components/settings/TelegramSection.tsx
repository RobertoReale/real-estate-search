import { useT } from "../../i18n";
import { useTelegramTest } from "../../queries/settings";
import type { Settings } from "../../types";
import { HelpSteps, Result, SecretStatus, SectionHeading } from "./controls";
import { Button, Checkbox, Input } from "../../ui";
import { Telegram } from "../../ui/icons";
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
  const test = useTelegramTest();

  return (
    <>
      <SectionHeading first icon={Telegram}>{t("settings.telegramTitle")}</SectionHeading>
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
          <Input data-action="settings.telegram.token" type="password"
            placeholder={t(settings.telegram_token_set ? "settings.tokenSaved" : "settings.tokenPlaceholder")}
            value={values.token} onChange={(e) => set("token", e.target.value)} />
          <div className="mt-1">
            <SecretStatus set={settings.telegram_token_set} dirty={!!values.token.trim()} />
          </div>
        </div>
        <Input data-action="settings.telegram.chatId" placeholder={t("settings.chatIdPlaceholder")}
          value={values.chatId} onChange={(e) => set("chatId", e.target.value)} />
        <Checkbox data-action="settings.telegram.actions" label={t("settings.telegramActions")}
          checked={values.actions} onCheckedChange={(v) => set("actions", v === true)} />
        <p className="text-xs opacity-70 -mt-2">{t("settings.telegramActionsHelp")}</p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Checkbox data-action="settings.telegram.enable" label={t("settings.enableTelegram")}
            checked={values.enabled} onCheckedChange={(v) => set("enabled", v === true)} />
          <Button data-action="settings.telegram.test" disabled={shell.anyBusy}
            onClick={() => shell.saveAndTest("telegram", () => test.mutateAsync(),
              () => t("settings.telegramTestSent"))}>
            {shell.busy === "telegram" ? t("settings.sending") : t("settings.saveAndTest")}
          </Button>
        </div>
        <Result feedback={shell.feedback} where="telegram" />
      </div>
    </>
  );
}
