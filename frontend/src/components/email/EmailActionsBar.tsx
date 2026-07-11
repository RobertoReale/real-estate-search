import type { ImportCheckProgress, ImportCheckSummary, Settings } from "../../types";
import { ProgressBar } from "../ProgressBar";

export type SortKey = "date" | "sqm_price" | "price";

interface Props {
  itemsCount: number;
  selectedCount: number;
  allSelected: boolean;
  onToggleSelectAll: () => void;
  onAcceptSelected: () => void;
  onDiscardSelected: () => void;
  onDiscardAllShown: () => void;
  onCheckAvailability: () => void;
  onSaveCookie: (cookie: string) => Promise<void>;
  cookieInput: string;
  onCookieInputChange: (val: string) => void;
  localSettings: Settings | null;
  busy: boolean;
  checking: boolean;
  checkProgress: ImportCheckProgress | null;
  checkSummary: ImportCheckSummary | null;
  goneCount: number;
  onDiscardGone: () => void;
  sort: SortKey;
  onSortChange: (sort: SortKey) => void;
}

export function EmailActionsBar({
  itemsCount,
  selectedCount,
  allSelected,
  onToggleSelectAll,
  onAcceptSelected,
  onDiscardSelected,
  onDiscardAllShown,
  onCheckAvailability,
  onSaveCookie,
  cookieInput,
  onCookieInputChange,
  localSettings,
  busy,
  checking,
  checkProgress,
  checkSummary,
  goneCount,
  onDiscardGone,
  sort,
  onSortChange,
}: Props) {
  if (itemsCount === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onToggleSelectAll}
          />
          Select all ({selectedCount})
        </label>
        <button
          className="btn-ghost text-xs"
          disabled={busy || selectedCount === 0}
          onClick={onAcceptSelected}>
          ✓ Accept selected
        </button>
        <button
          className="btn-ghost text-xs"
          disabled={busy || selectedCount === 0}
          onClick={onDiscardSelected}>
          ✕ Discard selected
        </button>
        <button
          className="btn-ghost text-xs text-rose-600 dark:text-rose-400"
          disabled={busy || itemsCount === 0}
          title="Discard every listing currently shown (the filters above still apply). Discards are remembered, so a re-scan won't bring them back — clear the queue, then scan again fresh."
          onClick={onDiscardAllShown}>
          🗑 Discard all ({itemsCount})
        </button>
        <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-lg p-1 bg-slate-50 dark:bg-slate-900/50">
          <input
            type="password"
            className="input text-xs py-0.5 px-1.5 w-28 sm:w-36"
            placeholder={
              localSettings?.datadome_cookie_set
                ? "DataDome cookie saved"
                : "Paste datadome cookie..."
            }
            value={cookieInput}
            onChange={(e) => onCookieInputChange(e.target.value)}
            title="Paste 'datadome' cookie from your real browser here to bypass blocks"
          />
          <button
            className="btn-ghost text-xs py-0.5 px-1.5"
            disabled={busy || checking || selectedCount === 0}
            title="Open each ad page once to see if it is still online. Slow on purpose (a few seconds apart)."
            onClick={() => {
              if (cookieInput.trim() && cookieInput !== "***") {
                onSaveCookie(cookieInput);
              } else {
                onCheckAvailability();
              }
            }}>
            🔎 Check if still online
          </button>
        </div>
        {goneCount > 0 && (
          <button
            className="btn-ghost text-xs text-rose-600 dark:text-rose-400"
            disabled={busy || checking}
            title="Discard every listing the portal confirmed as removed"
            onClick={onDiscardGone}>
            🚫 Discard the {goneCount} removed
          </button>
        )}
        <label className="flex items-center gap-1.5 text-xs t-muted ml-auto">
          Sort by
          <select
            className="input text-xs py-1"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortKey)}>
            <option value="date">Newest email</option>
            <option value="sqm_price">€/m² (cheapest first)</option>
            <option value="price">Price (lowest first)</option>
          </select>
        </label>
      </div>

      {checking && (
        <ProgressBar
          done={checkProgress?.done ?? 0}
          total={checkProgress?.total ?? 0}
          indeterminate={!checkProgress || checkProgress.total <= 0}>
          {checkProgress
            ? `Checking listing ${checkProgress.done} of ${checkProgress.total} — ${checkProgress.gone} already removed`
            : "Starting…"}{" "}
          One ad page every few seconds: visiting them in a burst is how a home IP gets
          blocked by the portals.
        </ProgressBar>
      )}

      {checkSummary && !checking && (
        <p className="text-xs t-muted">
          🔎 Checked {checkSummary.checked}:{" "}
          <strong>{checkSummary.gone} no longer online</strong>, {checkSummary.online}{" "}
          still there
          {checkSummary.unknown > 0 && (
            <>, {checkSummary.unknown} the portal would not answer for (blocked or unreachable — they keep whatever was known)</>
          )}
          .
          {checkSummary.cookie_refreshed ? (
            <span className="block mt-1">
              🔄 Grabbed a fresh DataDome cookie{" "}
              {checkSummary.cookie_refreshed === 1
                ? "once"
                : `${checkSummary.cookie_refreshed} times`}{" "}
              mid-check to get past a block.
            </span>
          ) : null}
          {checkSummary.last_error && (
            <span className="text-rose-600 dark:text-rose-400 block mt-1">
              ❌ Detail on last failure: {checkSummary.last_error}
            </span>
          )}
          {checkSummary.aborted && (
            <span className="text-amber-600 dark:text-amber-400">
              {" "}
              ⚠️ The portal started refusing, so the check stopped early rather than
              insisting — that would only deepen the block, and your scans need the same
              connection. Try again later.
            </span>
          )}
        </p>
      )}
    </div>
  );
}
