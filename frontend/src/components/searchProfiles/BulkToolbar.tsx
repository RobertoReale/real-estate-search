/** Select-all plus the bulk actions. Acting on every search one row at a time
 * is the tedium this removes: pausing them all before a holiday, muting a noisy
 * set. The "some but not all" indeterminate tick matters — without it the box
 * reads as "nothing selected" while a bulk bar is on screen. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";

export function BulkToolbar({ sp }: { sp: SearchProfilesState }) {
  const { t, profiles, selected, setSelected, allSelected, selectedProfiles, bulkBusy,
    runBulk, askDelete, groupSelected, channelOptions } = sp;
  return (
    <div className="flex flex-wrap items-center gap-2 mb-2 px-1">
      <label className="flex items-center gap-2 text-xs t-muted cursor-pointer">
        <input type="checkbox" checked={allSelected}
          // "some but not all" deserves its own tick: without it, the box
          // reads as "nothing selected" while a bulk bar is on screen
          ref={(el) => {
            if (el) el.indeterminate = selected.size > 0 && !allSelected;
          }}
          onChange={() => setSelected(
            allSelected ? new Set() : new Set(profiles.map((p) => p.id)),
          )} />
        {t("profiles.selectAll")}
      </label>
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs chip-blue px-2 py-1 rounded-lg font-medium">
            {t("profiles.selectedCount", { count: selected.size })}
          </span>
          <button className="btn-ghost !text-xs" disabled={bulkBusy}
            onClick={() => runBulk([...selected], "activate")}>
            {t("profiles.activate")}
          </button>
          <button className="btn-ghost !text-xs" disabled={bulkBusy}
            onClick={() => runBulk([...selected], "pause")}>
            {t("profiles.pause")}
          </button>
          {/* value stays on the placeholder: this is an action, not a state
              — the selection can hold searches with different channels */}
          <select className="input !py-1 !px-2 text-xs w-full sm:w-48"
            value="" disabled={bulkBusy}
            onChange={(e) =>
              runBulk([...selected], "notify", e.target.value)}>
            <option value="" disabled>{t("profiles.notificationsAction")}</option>
            {channelOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            className="btn-ghost !text-xs hover:!text-rose-500"
            disabled={bulkBusy}
            onClick={() => askDelete(selectedProfiles)}>
            {t("profiles.deleteAction")}
          </button>
          {selectedProfiles.length > 1 && (
            <button
              className="btn-ghost !text-xs !text-purple-600 dark:!text-purple-400 font-medium"
              disabled={bulkBusy}
              title={t("profiles.mergeSelectedTitle")}
              onClick={() => groupSelected(selectedProfiles)}>
              {t("profiles.mergeSelected")}
            </button>
          )}
          <button className="text-xs accent-link"
            onClick={() => setSelected(new Set())}>
            {t("profiles.clearSelection")}
          </button>
        </div>
      )}
    </div>
  );
}
