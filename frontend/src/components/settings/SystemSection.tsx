import { useState } from "react";
import { useT } from "../../i18n";
import { api } from "../../services/api";
import type { Settings } from "../../types";
import { Result, SecretStatus, SectionHeading } from "./controls";
import { errorText, useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  apiToken: string;
}

export function useSystemSection(): Section<Values> {
  return useSectionState<Values>(
    { apiToken: "" },
    // Unlike the other secrets this one comes back in clear to an already
    // authenticated caller, so Settings can show and clear it.
    (s) => ({ apiToken: s.api_auth_token ?? "" }),
    (v) => ({ api_auth_token: v.apiToken }),
  );
}

export function SystemSection(
  { section, settings, shell }: { section: Section<Values>; settings: Settings; shell: SettingsShell },
) {
  const t = useT();
  const { values, set } = section;
  const [restarting, setRestarting] = useState(false);

  /** Restart the backend and wait for it to come back, then reload the page so
   *  the whole UI is talking to the fresh process. Used after pulling a code
   *  update so the user need not hunt for the terminal window. */
  async function restartBackend() {
    if (!window.confirm(t("settings.restartConfirm"))) return;
    setRestarting(true);
    shell.setFeedback(null);
    try {
      await api.restartBackend();
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      // A 404/405 means THIS backend predates the restart route, so it cannot
      // restart itself — the classic bootstrap trap. Say so plainly instead of
      // polling (the process never went down) and pretending it worked.
      if (/Method Not Allowed|Not Found|Error 40[45]/i.test(raw)) {
        setRestarting(false);
        shell.setFeedback({ where: "global", ok: false, text: t("settings.restartTooOld") });
        return;
      }
      // Otherwise the socket dropped as the process went down — that is the
      // expected path; the poll below is the real "did it come back?" signal.
    }
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    await sleep(1500); // give it a moment to actually go down first
    const deadline = Date.now() + 40000;
    while (Date.now() < deadline) {
      try {
        await api.getScanStatus();
        window.location.reload();
        return;
      } catch {
        await sleep(1000);
      }
    }
    setRestarting(false);
    shell.setFeedback({ where: "global", ok: false, text: t("settings.restartNoReturn") });
  }

  /** Irreversible data reset. Confirmed in the browser (a second time for the
   * factory wipe), then the page reloads so the dashboard reflects the change. */
  async function runReset(
    scope: "dashboard" | "pricing-snapshots" | "factory",
    confirmText: string,
    doubleConfirm = false,
  ) {
    if (!window.confirm(confirmText)) return;
    if (doubleConfirm && !window.confirm(t("settings.lastChance"))) return;
    shell.setBusy("data");
    shell.setFeedback(null);
    try {
      const r = await api.resetData(scope);
      const removed = Object.entries(r.deleted)
        .map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ");
      shell.setFeedback({
        where: "data",
        ok: true,
        text: r.backup
          ? t("settings.resetDoneBackup", {
              removed: removed || t("settings.resetNothing"),
              backup: r.backup,
            })
          : t("settings.resetDone", { removed: removed || t("settings.resetNothing") }),
      });
      // Busy stays set on purpose: the page is about to reload, and releasing
      // the buttons first only invites a second click into a dying view.
      setTimeout(() => window.location.reload(), 1600);
    } catch (e) {
      shell.setFeedback({ where: "data", ok: false, text: errorText(e) });
      shell.setBusy(null);
    }
  }

  return (
    <>
      <SectionHeading>{t("settings.apiTokenTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.apiTokenNote")}</p>
      <input className="input w-full" type="password"
        placeholder={t("settings.apiTokenPlaceholder")}
        value={values.apiToken} onChange={(e) => set("apiToken", e.target.value)} />
      <div className="mt-1">
        <SecretStatus
          set={!!(settings.api_auth_token ?? "")}
          dirty={values.apiToken !== (settings.api_auth_token ?? "")} />
      </div>

      <Result feedback={shell.feedback} where="global" />

      <SectionHeading>{t("settings.backendTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.backendNote")}</p>
      <button className="btn-ghost w-full sm:w-auto" onClick={restartBackend}
        disabled={restarting || shell.anyBusy}>
        {restarting ? t("settings.restarting") : t("settings.restart")}
      </button>

      <div className="mt-8 pt-5 border-t border-rose-300/40 dark:border-rose-800/40">
        <h3 className="font-semibold text-sm uppercase text-rose-600 dark:text-rose-400 mb-1">
          {t("settings.dataTitle")}
        </h3>
        <p className="text-xs t-dim mb-3">{t("settings.dataNote")}</p>
        <div className="space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.clearDashboardName")}</span>
              {t("settings.clearDashboardBody")}
            </div>
            <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
              disabled={shell.anyBusy}
              onClick={() => runReset("dashboard", t("settings.clearDashboardConfirm"))}>
              {t("settings.clearDashboardButton")}
            </button>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.clearTrendsName")}</span>
              {t("settings.clearTrendsBody")}
            </div>
            <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
              disabled={shell.anyBusy}
              onClick={() => runReset("pricing-snapshots", t("settings.clearTrendsConfirm"))}>
              {t("settings.clearTrendsButton")}
            </button>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.factoryName")}</span>
              {t("settings.factoryBody")}
            </div>
            <button className="btn-ghost w-full sm:w-auto text-white bg-rose-600 hover:bg-rose-700 border-rose-600"
              disabled={shell.anyBusy}
              onClick={() => runReset("factory", t("settings.factoryConfirm"), true)}>
              {t("settings.factoryButton")}
            </button>
          </div>
        </div>
        <Result feedback={shell.feedback} where="data" />
      </div>
    </>
  );
}
