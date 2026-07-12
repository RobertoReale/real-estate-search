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
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <label className="flex items-center gap-1.5 text-xs font-medium t-muted cursor-pointer hover:text-blue-500 transition">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onToggleSelectAll}
            className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
          />
          Select all ({selectedCount})
        </label>
        <button
          className="btn py-1 px-2.5 text-xs bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onAcceptSelected}>
          ✓ Accept selected
        </button>
        <button
          className="btn py-1 px-2.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onDiscardSelected}>
          ✕ Discard selected
        </button>
        <button
          className="btn-ghost text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition py-1 px-2"
          disabled={busy || itemsCount === 0}
          title="Discard all currently shown listings (the filters above stay applied)."
          onClick={onDiscardAllShown}>
          🗑 Discard all ({itemsCount})
        </button>
        <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-xl p-1 bg-slate-50 dark:bg-slate-900/50 shadow-sm">
          <input
            type="password"
            className="input text-xs py-1 px-2 w-32 sm:w-40 bg-white dark:bg-slate-900"
            placeholder={
              localSettings?.datadome_cookie_set
                ? "DataDome cookie saved"
                : "Paste DataDome cookie…"
            }
            value={cookieInput}
            onChange={(e) => onCookieInputChange(e.target.value)}
            title="Paste the 'datadome' cookie from your browser here to get past the portals' blocks"
          />
          <button
            className="btn py-1 px-2.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-1"
            disabled={busy || checking || itemsCount === 0}
            title="Probe the portal pages to see which are still online and refresh their photos and data. If nothing is selected, it checks the not-yet-verified ones."
            onClick={async () => {
              if (cookieInput.trim() && cookieInput !== "***") {
                await onSaveCookie(cookieInput);
              }
              onCheckAvailability();
            }}>
            🔎 {selectedCount > 0 ? `Check selected (${selectedCount})` : "Check online availability"}
          </button>
        </div>
        {goneCount > 0 && (
          <button
            className="btn py-1 px-2.5 text-xs bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg transition animate-pulse"
            disabled={busy || checking}
            title="Discard in one go all listings the portal confirmed as removed/non-existent"
            onClick={onDiscardGone}>
            🚫 Discard the {goneCount} removed
          </button>
        )}
        <label className="flex items-center gap-1.5 text-xs font-medium t-muted ml-auto">
          Sort by:
          <select
            className="input text-xs py-1 px-2 rounded-lg"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortKey)}>
            <option value="date">Most recent email</option>
            <option value="sqm_price">€/m² (cheapest)</option>
            <option value="price">Price (lowest)</option>
          </select>
        </label>
      </div>

      {checking && (
        <ProgressBar
          done={checkProgress?.done ?? 0}
          total={checkProgress?.total ?? 0}
          indeterminate={!checkProgress || checkProgress.total <= 0}>
          {checkProgress
            ? `Checking listing ${checkProgress.done} of ${checkProgress.total} — ${checkProgress.gone} already removed…`
            : "Starting check…"}{" "}
          <span className="opacity-75 font-normal">
            (One page every 6 seconds to avoid the portals blocking the IP)
          </span>
        </ProgressBar>
      )}

      {checkSummary && !checking && (
        <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
          <p className="font-medium">
            🔎 Check result for {checkSummary.checked} listings:{" "}
            <strong className="text-rose-600 dark:text-rose-400">
              {checkSummary.gone} no longer online (removed)
            </strong>
            ,{" "}
            <strong className="text-emerald-600 dark:text-emerald-400">
              {checkSummary.online} still online and refreshed
            </strong>
            {checkSummary.unknown > 0 && (
              <span className="t-dim">
                {" "}
                ({checkSummary.unknown} inconclusive due to a block or network error)
              </span>
            )}
            .
          </p>
          {checkSummary.cookie_refreshed ? (
            <p className="text-blue-600 dark:text-blue-400 font-medium">
              🔄 DataDome cookie auto-refreshed{" "}
              {checkSummary.cookie_refreshed === 1
                ? "once"
                : `${checkSummary.cookie_refreshed} times`}{" "}
              during the check to get past the anti-bot controls.
            </p>
          ) : null}
          {checkSummary.last_error && (
            <p className="text-rose-600 dark:text-rose-400 font-medium">
              ❌ Last error detail: {checkSummary.last_error}
            </p>
          )}
          {checkSummary.aborted && (
            <p className="text-amber-600 dark:text-amber-400 font-semibold">
              ⚠️ The portal started blocking the requests, so the check was stopped to protect the network IP. Paste a fresh DataDome cookie or try again later.
            </p>
          )}
          {checkSummary.capped && !checkSummary.aborted && (
            <p className="t-dim">
              Per-run request limit reached: run the check again to continue with the rest.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
