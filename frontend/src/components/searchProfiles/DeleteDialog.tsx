/** The delete confirmation, portaled to <body>.
 *
 * Portaled because the panel around it is a `.glass`, and backdrop-blur makes it
 * the containing block of any `fixed` descendant — the overlay would cover the
 * panel instead of the viewport. (The other modals live in App.tsx, outside any
 * .glass, so they never hit this.)
 *
 * It shows counts rather than asking a bare yes/no because of what is *spared*:
 * a property another search still covers, or one the user curated, survives the
 * purge (invariant 20), and that is the number worth seeing before confirming. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { createPortal } from "react-dom";
import { getBaseName } from "../../utils/searchProfiles";

export function DeleteDialog({ sp }: { sp: SearchProfilesState }) {
  const { t, deleting, setDeleting, results, deleteBusy, deleteError, confirmDelete } = sp;
  if (!deleting) return null;
  return createPortal(
    <div data-action="profiles.delete.backdrop" className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-overlay backdrop-blur-sm"
      onClick={() => !deleteBusy && setDeleting(null)}>
      <div data-action="profiles.delete.panel" className="glass rounded-2xl max-w-md w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-bold mb-2">
          {deleting.length === 1
            ? t("profiles.deleteOne", { name: deleting[0].name })
            : t("profiles.deleteGroup", {
                name: getBaseName(deleting[0].name),
                count: deleting.length,
              })}
        </h2>
        <p className="text-sm t-muted">
          {t(deleting.length === 1 ? "profiles.deleteBodyOne" : "profiles.deleteBodyMany")}
        </p>
        {deleting.length > 1 && (
          <ul className="mt-2 text-xs t-muted space-y-0.5 max-h-32 overflow-y-auto">
            {deleting.map((p) => <li key={p.id} className="truncate">· {p.name} ({p.portal})</li>)}
          </ul>
        )}

        <div className="mt-4 p-3 rounded-xl panel text-sm">
          {results === null && !deleteError && (
            <p className="t-muted">{t("profiles.countingResults")}</p>
          )}
          {results && results.tracked === 0 && (
            <p className="t-muted">
              {t(
                deleting.length === 1
                  ? "profiles.noneAttributableOne"
                  : "profiles.noneAttributableMany",
              )}
            </p>
          )}
          {results && results.tracked > 0 && (
            <>
              <p>
                {t(deleting.length === 1 ? "profiles.foundOne" : "profiles.foundMany", {
                  tracked: results.tracked,
                  deletable: results.deletable,
                })}
              </p>
              {/* the spared ones are the whole reason this dialog shows
                  numbers rather than just asking yes/no */}
              {(results.kept_shared > 0 || results.kept_curated > 0) && (
                <ul className="mt-2 space-y-0.5 text-xs t-muted">
                  {results.kept_shared > 0 && (
                    <li>{t("profiles.keptShared", { count: results.kept_shared })}</li>
                  )}
                  {results.kept_curated > 0 && (
                    <li>{t("profiles.keptCurated", { count: results.kept_curated })}</li>
                  )}
                </ul>
              )}
              {results.deletable > 0 && (
                <p className="mt-2 text-xs accent-bad">
                  {t("profiles.deleteIrreversible")}
                </p>
              )}
            </>
          )}
        </div>

        {deleteError && <p className="accent-bad text-xs mt-3">{deleteError}</p>}

        <div className="flex flex-wrap gap-2 mt-5">
          <button data-action="profiles.delete.cancel" className="btn-ghost" disabled={deleteBusy}
            onClick={() => setDeleting(null)}>
            {t("common.cancel")}
          </button>
          <button data-action="profiles.delete.keepResults" className="btn-ghost flex-1" disabled={deleteBusy}
            onClick={() => confirmDelete(false)}>
            {t("profiles.keepResults")}
          </button>
          <button data-action="profiles.delete.withResults" className="btn-primary flex-1 !bg-negative hover:!bg-negative-hover"
            disabled={deleteBusy || !results || results.deletable === 0}
            onClick={() => confirmDelete(true)}>
            {deleteBusy
              ? t("profiles.deleting")
              : t("profiles.deleteWith", { count: results?.deletable ?? 0 })}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
