import type { EmailScanParams, EmailScanProgress, EmailScanSummary } from "../../types";
import { ProgressBar } from "../ProgressBar";

function progressLabel(p: EmailScanProgress): string {
  if (p.phase === "connecting") return "Connecting to your mailbox…";
  if (p.phase === "searching") return "Searching the inbox…";
  if (p.phase === "fetching" && p.emails_total > 0) {
    return (
      `Reading email ${p.emails_done} of ${p.emails_total}` +
      ` — ${p.staged} new listing${p.staged === 1 ? "" : "s"} staged`
    );
  }
  return "Starting…";
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
  return (
    <>
      <div className="grid grid-cols-2 gap-3 items-end p-3 rounded-xl panel sm:flex sm:flex-wrap">
        <div className="col-span-2 flex flex-col gap-1">
          <label className="text-xs t-muted">Look for</label>
          <select
            className="input w-full sm:w-56"
            value={scanParams.mode}
            onChange={(e) =>
              onScanParamsChange((p) => ({
                ...p,
                mode: e.target.value as EmailScanParams["mode"],
              }))
            }>
            <option value="portals">Portal alert emails</option>
            <option value="address">Specific sender(s)</option>
            <option value="any">Any email linking a portal ad</option>
          </select>
        </div>
        {scanParams.mode === "address" && (
          <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[16rem]">
            <label
              className="text-xs t-muted"
              title="Their emails must link an Immobiliare.it or Idealista.it ad: a link to the agency's own site cannot be imported">
              Senders (comma-separated addresses or domains)
            </label>
            <input
              className="input w-full"
              placeholder="e.g. agenzia@example.com, immobiliare.it"
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
          <label className="text-xs t-muted">Period</label>
          <select
            className="input w-full sm:w-36"
            value={scanParams.since_days}
            onChange={(e) =>
              onScanParamsChange((p) => ({
                ...p,
                since_days: Number(e.target.value),
              }))
            }>
            <option value={30}>Last month</option>
            <option value={180}>Last 6 months</option>
            <option value={365}>Last year</option>
            <option value={1825}>Last 5 years</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label
            className="text-xs t-muted"
            title="Newest messages first; re-run the scan to go deeper (already imported listings are skipped)">
            Max emails
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
          {scanning ? "Scanning inbox…" : "Scan inbox"}
        </button>
      </div>

      {scanning && (
        <ProgressBar
          done={progress?.emails_done ?? 0}
          total={progress?.emails_total ?? 0}
          indeterminate={!progress || progress.emails_total <= 0}>
          {progress ? progressLabel(progress) : "Starting…"} Large mailboxes take a few
          minutes; you can keep using the dashboard meanwhile.
        </ProgressBar>
      )}

      {summary && !scanning && (
        <p className="text-xs t-muted">
          ✅ Scanned {summary.emails_scanned} emails ({summary.emails_with_listings} with
          listings) — <strong>{summary.imported} new listings staged</strong>,{" "}
          {summary.already_tracked} already tracked by your searches,{" "}
          {summary.already_imported} seen in a previous scan.
          {summary.blank_links > 0 && (
            <>
              {" "}
              {summary.blank_links} link
              {summary.blank_links === 1 ? " was" : "s were"} skipped: the email gave no
              price, size or name to review them by.
            </>
          )}
          {summary.blank_removed > 0 && (
            <>
              {" "}
              {summary.blank_removed} such row
              {summary.blank_removed === 1 ? "" : "s"} left by earlier scans
              {summary.blank_removed === 1 ? " was" : " were"} cleaned up.
            </>
          )}
        </p>
      )}
    </>
  );
}
