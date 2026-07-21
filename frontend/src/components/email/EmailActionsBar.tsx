import { useT } from "../../i18n";
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
  const t = useT();
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
          {t("email.selectAll", { count: selectedCount })}
        </label>
        <button
          className="btn py-1 px-2.5 text-xs bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onAcceptSelected}>
          {t("email.acceptSelected")}
        </button>
        <button
          className="btn py-1 px-2.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onDiscardSelected}>
          {t("email.discardSelected")}
        </button>
        <button
          className="btn-ghost text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition py-1 px-2"
          disabled={busy || itemsCount === 0}
          title={t("email.discardAllTitle")}
          onClick={onDiscardAllShown}>
          {t("email.discardAll", { count: itemsCount })}
        </button>
        <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-xl p-1 bg-slate-50 dark:bg-slate-900/50 shadow-sm">
          <input
            type="password"
            className="input text-xs py-1 px-2 w-32 sm:w-40 bg-white dark:bg-slate-900"
            placeholder={t(
              localSettings?.datadome_cookie_set ? "email.cookieSaved" : "email.cookiePaste",
            )}
            value={cookieInput}
            onChange={(e) => onCookieInputChange(e.target.value)}
            title={t("email.cookieTitle")}
          />
          <button
            className="btn py-1 px-2.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-1"
            disabled={busy || checking || itemsCount === 0}
            title={t("email.checkTitle")}
            onClick={async () => {
              if (cookieInput.trim() && cookieInput !== "***") {
                await onSaveCookie(cookieInput);
              }
              onCheckAvailability();
            }}>
            {selectedCount > 0
              ? t("email.checkSelected", { count: selectedCount })
              : t("email.checkAll")}
          </button>
        </div>
        {goneCount > 0 && (
          <button
            className="btn py-1 px-2.5 text-xs bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg transition animate-pulse"
            disabled={busy || checking}
            title={t("email.discardGoneTitle")}
            onClick={onDiscardGone}>
            {t("email.discardGone", { count: goneCount })}
          </button>
        )}
        <label className="flex items-center gap-1.5 text-xs font-medium t-muted ml-auto">
          {t("email.sortBy")}
          <select
            className="input text-xs py-1 px-2 rounded-lg"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortKey)}>
            <option value="date">{t("email.sortDate")}</option>
            <option value="sqm_price">{t("email.sortSqmPrice")}</option>
            <option value="price">{t("email.sortPrice")}</option>
          </select>
        </label>
      </div>

      {checking && (
        <ProgressBar
          done={checkProgress?.done ?? 0}
          total={checkProgress?.total ?? 0}
          indeterminate={!checkProgress || checkProgress.total <= 0}>
          {checkProgress
            ? t("email.checkProgress", {
                done: checkProgress.done,
                total: checkProgress.total,
                gone: checkProgress.gone,
              })
            : t("app.checkStarting")}{" "}
          <span className="opacity-75 font-normal">{t("email.checkPacing")}</span>
        </ProgressBar>
      )}

      {checkSummary && !checking && (
        <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
          <p className="font-medium">
            {t("email.checkResult", { count: checkSummary.checked })}{" "}
            <strong className="text-rose-600 dark:text-rose-400">
              {t("email.checkGone", { count: checkSummary.gone })}
            </strong>
            ,{" "}
            <strong className="text-emerald-600 dark:text-emerald-400">
              {t("email.checkOnline", { count: checkSummary.online })}
            </strong>
            {checkSummary.unknown > 0 && (
              <span className="t-dim">
                {t("email.checkUnknown", { count: checkSummary.unknown })}
              </span>
            )}
            .
          </p>
          {checkSummary.cookie_refreshed ? (
            <p className="text-blue-600 dark:text-blue-400 font-medium">
              {t(
                checkSummary.cookie_refreshed === 1
                  ? "email.cookieRefreshedOnce"
                  : "email.cookieRefreshed",
                { count: checkSummary.cookie_refreshed },
              )}
            </p>
          ) : null}
          {checkSummary.last_error && (
            <p className="text-rose-600 dark:text-rose-400 font-medium">
              {t("email.lastErrorDetail", { error: checkSummary.last_error })}
            </p>
          )}
          {checkSummary.aborted && (
            <p className="text-amber-600 dark:text-amber-400 font-semibold">
              {t("email.checkAborted")}
            </p>
          )}
          {checkSummary.capped && !checkSummary.aborted && (
            <p className="t-dim">{t("app.summaryCapped")}</p>
          )}
        </div>
      )}
    </div>
  );
}
