/** Select-all plus the bulk actions. Acting on every search one row at a time
 * is the tedium this removes: pausing them all before a holiday, muting a noisy
 * set. The "some but not all" indeterminate tick matters — without it the box
 * reads as "nothing selected" while a bulk bar is on screen. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { Button, Chip } from "../../ui";
import { Delete, Merged, Paused, Run } from "../../ui/icons";

export function BulkToolbar({ sp }: { sp: SearchProfilesState }) {
  const { t, profiles, selected, setSelected, allSelected, selectedProfiles, bulkBusy,
    runBulk, askDelete, groupSelected, channelOptions } = sp;
  return (
    <div className="flex flex-wrap items-center gap-2 mb-2 px-1">
      <label className="flex items-center gap-2 text-xs t-muted cursor-pointer">
        <input data-action="profiles.bulk.selectAll" type="checkbox" checked={allSelected}
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
          <Chip tone="accent" size="md">
            {t("profiles.selectedCount", { count: selected.size })}
          </Chip>
          <Button data-action="profiles.bulk.activate" size="sm" disabled={bulkBusy}
            onClick={() => runBulk([...selected], "activate")}>
            <Run /> {t("profiles.activate")}
          </Button>
          <Button data-action="profiles.bulk.pause" size="sm" disabled={bulkBusy}
            onClick={() => runBulk([...selected], "pause")}>
            <Paused /> {t("profiles.pause")}
          </Button>
          {/* value stays on the placeholder: this is an action, not a state
              — the selection can hold searches with different channels */}
          <select data-action="profiles.bulk.notify" className="input !py-1 !px-2 text-xs w-full sm:w-48"
            value="" disabled={bulkBusy}
            onChange={(e) =>
              runBulk([...selected], "notify", e.target.value)}>
            <option value="" disabled>{t("profiles.notificationsAction")}</option>
            {channelOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <Button data-action="profiles.bulk.delete" size="sm" tone="negative"
            disabled={bulkBusy}
            onClick={() => askDelete(selectedProfiles)}>
            <Delete /> {t("profiles.deleteAction")}
          </Button>
          {selectedProfiles.length > 1 && (
            <Button data-action="profiles.bulk.merge" size="sm"
              className="text-tag-ink"
              disabled={bulkBusy}
              title={t("profiles.mergeSelectedTitle")}
              onClick={() => groupSelected(selectedProfiles)}>
              <Merged /> {t("profiles.mergeSelected")}
            </Button>
          )}
          <button data-action="profiles.bulk.clear" className="text-xs accent-link"
            onClick={() => setSelected(new Set())}>
            {t("profiles.clearSelection")}
          </button>
        </div>
      )}
    </div>
  );
}
