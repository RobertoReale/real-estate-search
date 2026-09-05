import { useRef, type ChangeEvent } from "react";
import { formatDateTime, formatNumber, useT } from "../../i18n";
import {
  useBackups, useCreateBackup, useImportBackup, useResetData, useRestartBackend,
  useRestoreBackup,
} from "../../queries/maintenance";
import { api, authToken, AuthError, fetchBackup } from "../../services/api";
import type { BackupFile, Settings } from "../../types";
import { errorText, useToasts } from "../Toast";
import { Result, SecretStatus, SectionHeading } from "./controls";
import { Button, Input } from "../../ui";
import { Backup, Import, Locked, Restart } from "../../ui/icons";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  apiToken: string;
}

/** A file size the way a person reads one. Whole kilobytes below a megabyte,
 *  one decimal above: the point is telling a full database from an empty one at
 *  a glance, not accounting for bytes. */
function formatSize(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return mb < 1
    ? `${formatNumber(Math.max(1, Math.round(bytes / 1024)))} kB`
    : `${formatNumber(mb, { maximumFractionDigits: 1 })} MB`;
}

/** Hand a URL to the browser as a download. An anchor rather than
 *  `window.open`: `download` is what makes the browser save the file under the
 *  name we chose instead of navigating away from the dashboard. */
function handOff(url: string, filename: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
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
  const toasts = useToasts();
  const { values, set } = section;
  const filePicker = useRef<HTMLInputElement>(null);

  const list = useBackups();
  const createBackup = useCreateBackup();
  const importBackup = useImportBackup();
  const restoreBackup = useRestoreBackup();
  const resetData = useResetData();
  const restart = useRestartBackend();

  const backups: BackupFile[] | null = list.data ? list.data.backups : list.isError ? [] : null;
  const folder = list.data?.folder ?? "";
  // A backend older than these routes answers 404, which is a perfectly
  // ordinary thing to meet after pulling an update without restarting.
  const listError = list.isError ? errorText(list.error) : "";
  const restarting = restart.isPending;

  /** Restart the backend and wait for it to come back, then reload the page so
   *  the whole UI is talking to the fresh process. Used after pulling a code
   *  update so the user need not hunt for the terminal window.
   *
   *  The waiting is inside the mutation, because the request itself does not
   *  return — the socket drops as the process goes down — so a resolved
   *  mutation here means the restart did *not* complete. */
  async function restartBackend() {
    if (!window.confirm(t("settings.restartConfirm"))) return;
    shell.setFeedback(null);
    try {
      // A resolved mutation is the bad outcome here, so it is a message about
      // something that did not happen rather than a confirmation.
      const outcome = await restart.mutateAsync();
      toasts.show({
        tone: "error",
        text: t(outcome === "too-old" ? "settings.restartTooOld" : "settings.restartNoReturn"),
      });
    } catch (e) {
      toasts.fail(e, { retry: () => restartBackend() });
    }
  }

  /** Copy the database right now, whatever the daily throttle thinks — the
   *  button pressed before doing something risky. */
  async function takeBackup() {
    shell.setBusy("backups");
    shell.setFeedback(null);
    try {
      const made = await createBackup.mutateAsync();
      shell.setFeedback({ where: "backups", text: t("settings.backupTaken", { name: made.name }) });
    } catch (e) {
      toasts.fail(e, { retry: () => takeBackup() });
    } finally {
      shell.setBusy(null);
    }
  }

  /** Save one copy to the user's downloads. Without a token the browser can
   *  fetch it itself (the response names the file); with one, a navigation
   *  cannot carry the header, so it is fetched and handed over as a blob —
   *  the same split the dossier export makes. */
  async function download(name: string) {
    shell.setFeedback(null);
    if (!authToken.get()) {
      handOff(api.backupUrl(name), name);
      return;
    }
    shell.setBusy("backups");
    try {
      const url = URL.createObjectURL(await fetchBackup(name));
      handOff(url, name);
      // revoking at once cancels the transfer in some browsers
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      // an AuthError has already raised the token prompt
      if (!(e instanceof AuthError)) {
        toasts.fail(e, { retry: () => download(name) });
      }
    } finally {
      shell.setBusy(null);
    }
  }

  /** Bring in a `case.db` carried from another install. It joins the list; it
   *  does not become the live database until the user restores it. */
  async function importPicked(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // cleared immediately, or picking the same file twice would not fire
    event.target.value = "";
    if (!file) return;
    shell.setBusy("backups");
    shell.setFeedback(null);
    try {
      const added = await importBackup.mutateAsync(file);
      shell.setFeedback({ where: "backups", text: t("settings.backupImported", { name: added.name }) });
    } catch (e) {
      // No retry: the picked file is gone from the input by now, so the button
      // would have nothing to send.
      toasts.fail(e);
    } finally {
      shell.setBusy(null);
    }
  }

  /** Replace the live database with a copy. The most destructive action in the
   *  app, so it asks for a typed word rather than a click — and the backend
   *  copies the current state aside first, which the confirmation says. */
  async function restore(file: BackupFile) {
    const word = t("settings.restoreConfirmWord");
    const typed = window.prompt(
      t("settings.restoreConfirm", { date: formatDateTime(file.taken_at), word }),
    );
    if (typed?.trim().toLocaleUpperCase() !== word.toLocaleUpperCase()) return;
    shell.setBusy("backups");
    shell.setFeedback(null);
    try {
      const r = await restoreBackup.mutateAsync(file.name);
      shell.setFeedback({
        where: "backups",
        text: r.backup
          ? t("settings.restoreDoneBackup", { name: r.restored, backup: r.backup })
          : t("settings.restoreDone", { name: r.restored }),
      });
      // Busy stays set: the page is about to reload, and the whole UI is now
      // looking at a different database.
      setTimeout(() => window.location.reload(), 1800);
    } catch (e) {
      // No retry offered on the most destructive action in the app: it asks for
      // a typed word for a reason, and a one-click way to ask again undoes that.
      toasts.fail(e);
      shell.setBusy(null);
    }
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
      const r = await resetData.mutateAsync(scope);
      const removed = Object.entries(r.deleted)
        .map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ");
      shell.setFeedback({
        where: "data",
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
      // Same reason as the restore above: this one asked twice on purpose.
      toasts.fail(e);
      shell.setBusy(null);
    }
  }

  return (
    <>
      <SectionHeading icon={Locked}>{t("settings.apiTokenTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.apiTokenNote")}</p>
      <Input data-action="settings.system.apiToken" type="password"
        placeholder={t("settings.apiTokenPlaceholder")}
        value={values.apiToken} onChange={(e) => set("apiToken", e.target.value)} />
      <div className="mt-1">
        <SecretStatus
          set={!!(settings.api_auth_token ?? "")}
          dirty={values.apiToken !== (settings.api_auth_token ?? "")} />
      </div>

      <Result feedback={shell.feedback} where="global" />

      <SectionHeading icon={Restart}>{t("settings.backendTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.backendNote")}</p>
      <Button data-action="settings.system.restart" className="w-full sm:w-auto" onClick={restartBackend}
        disabled={restarting || shell.anyBusy}>
        <Restart /> {restarting ? t("settings.restarting") : t("settings.restart")}
      </Button>

      <SectionHeading icon={Backup}>{t("settings.backupsTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-3">{t("settings.backupsNote")}</p>
      <div className="flex flex-col sm:flex-row gap-2">
        <Button data-action="settings.system.backupNow" className="w-full sm:w-auto" onClick={takeBackup}
          disabled={shell.anyBusy}>
          <Backup /> {t("settings.backupTakeNow")}
        </Button>
        <Button data-action="settings.system.backupImport" className="w-full sm:w-auto"
          onClick={() => filePicker.current?.click()} disabled={shell.anyBusy}>
          <Import /> {t("settings.backupImport")}
        </Button>
        {/* .db only as a hint: the file is proved to be one of ours by the
            backend before anything live is touched, never by its name */}
        {/* Not the `Input` primitive: this one is never drawn — it is the file
            picker the button above opens — so a control surface would style
            nothing, and it needs a ref, which the primitive does not forward. */}
        <input data-action="settings.system.backupFile" ref={filePicker} type="file"
          accept=".db,.sqlite,application/vnd.sqlite3" className="hidden" onChange={importPicked} />
      </div>
      {folder && <p className="text-2xs t-dim mt-2 break-all">{t("settings.backupsFolder", { folder })}</p>}
      {/* In place of the list rather than in a toast: this is what there is to
          read where the copies would have been, and it is not the result of
          anything the user just pressed. */}
      {listError && <p className="text-xs t-muted mt-2">{listError}</p>}
      {backups !== null && backups.length === 0 && !listError && (
        <p className="text-xs t-dim mt-2">{t("settings.backupsEmpty")}</p>
      )}
      {backups && backups.length > 0 && (
        <ul className="mt-2 rounded-lg panel divide-y divide-line">
          {backups.map((file) => (
            <li key={file.name}
              className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-3 px-3 py-2">
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium t-body">{formatDateTime(file.taken_at)}</div>
                <div className="text-2xs t-dim">
                  {t(`settings.backupKind.${file.kind}`)} · {formatSize(file.size_bytes)} ·{" "}
                  {file.revision
                    ? t("settings.backupSchema", { revision: file.revision })
                    : t("settings.backupSchemaUnknown")}
                </div>
              </div>
              <div className="flex gap-2">
                <Button data-action="settings.system.backupDownload" size="sm" disabled={shell.anyBusy}
                  onClick={() => download(file.name)}>
                  {t("settings.backupDownload")}
                </Button>
                <Button data-action="settings.system.backupRestore" size="sm" tone="negative"
                  disabled={shell.anyBusy} onClick={() => restore(file)}>
                  {t("settings.backupRestore")}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Result feedback={shell.feedback} where="backups" />

      <div className="mt-8 pt-5 border-t border-negative-line-soft">
        <h3 className="font-semibold text-sm uppercase text-negative-ink mb-1">
          {t("settings.dataTitle")}
        </h3>
        <p className="text-xs t-dim mb-3">{t("settings.dataNote")}</p>
        <div className="space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.clearDashboardName")}</span>
              {t("settings.clearDashboardBody")}
            </div>
            <Button data-action="settings.system.resetDashboard" tone="negative" className="w-full sm:w-auto"
              disabled={shell.anyBusy}
              onClick={() => runReset("dashboard", t("settings.clearDashboardConfirm"))}>
              {t("settings.clearDashboardButton")}
            </Button>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.clearTrendsName")}</span>
              {t("settings.clearTrendsBody")}
            </div>
            <Button data-action="settings.system.resetTrends" tone="negative" className="w-full sm:w-auto"
              disabled={shell.anyBusy}
              onClick={() => runReset("pricing-snapshots", t("settings.clearTrendsConfirm"))}>
              {t("settings.clearTrendsButton")}
            </Button>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
            <div className="flex-1 text-xs t-body">
              <span className="font-medium">{t("settings.factoryName")}</span>
              {t("settings.factoryBody")}
            </div>
            <Button data-action="settings.system.resetFactory" variant="solid" tone="negative"
              className="w-full sm:w-auto"
              disabled={shell.anyBusy}
              onClick={() => runReset("factory", t("settings.factoryConfirm"), true)}>
              {t("settings.factoryButton")}
            </Button>
          </div>
        </div>
        <Result feedback={shell.feedback} where="data" />
      </div>
    </>
  );
}
