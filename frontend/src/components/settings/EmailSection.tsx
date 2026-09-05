import { useT } from "../../i18n";
import { useEmailTest } from "../../queries/settings";
import type { Settings } from "../../types";
import { HelpSteps, Link, Result, SecretStatus, SectionHeading } from "./controls";
import { Button, Checkbox, Input } from "../../ui";
import { Email } from "../../ui/icons";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  enabled: boolean;
  host: string;
  port: number;
  user: string;
  password: string;
  from: string;
  to: string;
}

export function useEmailSection(): Section<Values> {
  return useSectionState<Values>(
    { enabled: false, host: "", port: 587, user: "", password: "", from: "", to: "" },
    (s) => ({
      enabled: s.email_enabled,
      host: s.smtp_host,
      port: s.smtp_port,
      user: s.smtp_user,
      password: "", // write-only, like the Telegram token
      from: s.email_from,
      to: s.email_to,
    }),
    (v) => {
      const p: Partial<Settings> = {
        email_enabled: v.enabled,
        smtp_host: v.host,
        smtp_port: v.port,
        smtp_user: v.user,
        email_from: v.from,
        email_to: v.to,
      };
      // Empty means "keep the stored one". The value is sent untrimmed on
      // purpose: pasted app passwords keep their display spaces, and
      // save_settings is what strips them.
      if (v.password.trim()) p.smtp_password = v.password;
      return p;
    },
  );
}

export function EmailSection(
  { section, settings, shell }: { section: Section<Values>; settings: Settings; shell: SettingsShell },
) {
  const t = useT();
  const { values, set } = section;
  const test = useEmailTest();

  return (
    <>
      <SectionHeading icon={Email}>{t("settings.emailTitle")}</SectionHeading>
      <HelpSteps
        summary={t("settings.emailHelp")}
        steps={[
          t("settings.emStep1"),
          <>
            {t("settings.emStep2a")}
            <Link href="https://myaccount.google.com/signinoptions/twosv">
              {t("settings.emStep2Link")}
            </Link>
            {t("settings.emStep2b")}
          </>,
          <>
            {t("settings.emStep3a")}
            <Link href="https://myaccount.google.com/apppasswords">
              myaccount.google.com/apppasswords
            </Link>
            {t("settings.emStep3b")}
          </>,
          t("settings.emStep4"),
          t("settings.emStep5"),
        ]}
      />
      <div className="space-y-3">
        {/* host and port share a row only when there is room for both: at
            phone width a 1/3-wide host field cannot show its own hostname */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input data-action="settings.email.host" className="sm:col-span-2" placeholder={t("settings.smtpHost")}
            value={values.host} onChange={(e) => set("host", e.target.value)} />
          <Input data-action="settings.email.port" type="number" placeholder="587"
            aria-label={t("settings.smtpPortTitle")}
            title={t("settings.smtpPortTitle")}
            value={values.port} onChange={(e) => set("port", Number(e.target.value))} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input data-action="settings.email.user" placeholder={t("settings.smtpUser")}
            value={values.user} onChange={(e) => set("user", e.target.value)} />
          <div>
            <Input data-action="settings.email.password" type="password"
              placeholder={t(settings.smtp_password_set ? "settings.passwordSaved" : "settings.appPassword")}
              value={values.password} onChange={(e) => set("password", e.target.value)} />
            <div className="mt-1">
              <SecretStatus set={settings.smtp_password_set} dirty={!!values.password.trim()} />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input data-action="settings.email.from" placeholder={t("settings.emailFrom")}
            value={values.from} onChange={(e) => set("from", e.target.value)} />
          <Input data-action="settings.email.to" placeholder={t("settings.emailTo")}
            value={values.to} onChange={(e) => set("to", e.target.value)} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Checkbox data-action="settings.email.enable" label={t("settings.enableEmail")}
            checked={values.enabled} onCheckedChange={(v) => set("enabled", v === true)} />
          <Button data-action="settings.email.test" disabled={shell.anyBusy}
            onClick={() => shell.saveAndTest("email", () => test.mutateAsync(),
              () => t("settings.emailTestSent", {
                to: values.to || t("settings.theRecipient"),
              }))}>
            {shell.busy === "email" ? t("settings.sending") : t("settings.saveAndTest")}
          </Button>
        </div>
        <Result feedback={shell.feedback} where="email" />
      </div>
    </>
  );
}
