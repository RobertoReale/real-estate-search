import { translateCurrent, useT } from "../../i18n";
import type { EmailScanParams, EmailScanProgress, EmailScanSummary } from "../../types";
import { ProgressBar } from "../ProgressBar";

function progressLabel(p: EmailScanProgress): string {
  if (p.phase === "connecting") return translateCurrent("email.phaseConnecting");
  if (p.phase === "searching") return translateCurrent("email.phaseSearching");
  if (p.phase === "fetching" && p.emails_total > 0) {
    return translateCurrent(
      p.staged === 1 ? "email.phaseReadingOne" : "email.phaseReading",
      { done: p.emails_done, total: p.emails_total, staged: p.staged },
    );
  }
  return translateCurrent("email.phaseStarting");
}

interface Props {
  scanParams: EmailScanParams;
  onScanParamsChange: (updater: (p: EmailScanParams) => EmailScanParams) => void;
  onScan: () => void;
  scanning: boolean;
  progress: EmailScanProgress | null;
  imapReady: boolean;
  summary: EmailScanSummary | null;
}

export function EmailScanForm({
  scanParams,
  onScanParamsChange,
  onScan,
  scanning,
  progress,
  imapReady,
  summary,
}: Props) {
  const t = useT();
  return (
    <>
      <div className="grid grid-cols-2 gap-3 items-end p-3 rounded-xl panel sm:flex sm:flex-wrap">
        <div className="col-span-2 flex flex-col gap-1">
          <label className="text-xs t-muted">{t("email.lookFor")}</label>
          <select
            className="input w-full sm:w-56"
            value={scanParams.mode}
            onChange={(e) =>
              onScanParamsChange((p) => ({
                ...p,
                mode: e.target.value as EmailScanParams["mode"],
              }))
            }>
            <option value="portals">{t("email.modePortals")}</option>
            <option value="address">{t("email.modeAddress")}</option>
            <option value="any">{t("email.modeAny")}</option>
          </select>
        </div>
        {scanParams.mode === "address" && (
          <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[16rem]">
            <label
              className="text-xs t-muted"
              title={t("email.sendersTitle")}>
              {t("email.senders")}
            </label>
            <input
              className="input w-full"
              placeholder={t("email.sendersPlaceholder")}
              value={scanParams.senders}
              onChange={(e) =>
                onScanParamsChange((p) => ({
                  ...p,
                  senders: e.target.value,
                }))
              }
            />
          </div>
        )}
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("email.period")}</label>
          <select
            className="input w-full sm:w-36"
            value={scanParams.since_days}
            onChange={(e) =>
              onScanParamsChange((p) => ({
                ...p,
                since_days: Number(e.target.value),
              }))
            }>
            <option value={30}>{t("email.lastMonth")}</option>
            <option value={180}>{t("email.last6Months")}</option>
            <option value={365}>{t("email.lastYear")}</option>
            <option value={1825}>{t("email.last5Years")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label
            className="text-xs t-muted"
            title={t("email.maxEmailsTitle")}>
            {t("email.maxEmails")}
          </label>
          <select
            className="input w-full sm:w-28"
            value={scanParams.max_emails}
            onChange={(e) =>
              onScanParamsChange((p) => ({
                ...p,
                max_emails: Number(e.target.value),
              }))
            }>
            {[50, 200, 500, 1000].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn-primary col-span-2 sm:w-auto"
          onClick={onScan}
          disabled={
            scanning ||
            !imapReady ||
            (scanParams.mode === "address" && !scanParams.senders.trim())
          }>
          {scanning ? t("email.scanning") : t("email.scan")}
        </button>
      </div>

      {scanning && (
        <ProgressBar
          done={progress?.emails_done ?? 0}
          total={progress?.emails_total ?? 0}
          indeterminate={!progress || progress.emails_total <= 0}>
          {progress ? progressLabel(progress) : t("email.phaseStarting")}{" "}
          {t("email.scanNote")}
        </ProgressBar>
      )}

      {summary && !scanning && (
        <p className="text-xs t-muted">
          {t("email.scanSummary", {
            emails: summary.emails_scanned,
            withListings: summary.emails_with_listings,
            imported: summary.imported,
            tracked: summary.already_tracked,
            seen: summary.already_imported,
          })}
          {summary.blank_links > 0 &&
            t(summary.blank_links === 1 ? "email.blankLinksOne" : "email.blankLinks", {
              count: summary.blank_links,
            })}
          {summary.blank_removed > 0 &&
            t(summary.blank_removed === 1 ? "email.blankRemovedOne" : "email.blankRemoved", {
              count: summary.blank_removed,
            })}
        </p>
      )}
    </>
  );
}
