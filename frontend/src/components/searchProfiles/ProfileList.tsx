/** The monitored searches themselves, one row per group (a "group" being the
 * same search on both portals, folded into one card). */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { formatNumber } from "../../i18n";
import { PortalBadge } from "../PortalBadge";
import { statusBadge } from "./constants";
import { combinedKeywords } from "./helpers";

export function ProfileList({ sp }: { sp: SearchProfilesState }) {
  const { t, settings, profiles, groupedProfiles, selected, toggleGroup, channelOptions,
    runBulk, editGroup, separateGroup, askDelete } = sp;
  return (
    <ul className="space-y-2">
      {groupedProfiles.map((group) => {
        const badge = statusBadge[group.last_run_status];
        const channel = channelOptions.find((o) => o.value === group.notify_channels)
          ?? channelOptions[0];
        const isGroupSelected = group.ids.length > 0 && group.ids.every((id) => selected.has(id));
        const isGroupIndeterminate = !isGroupSelected && group.ids.some((id) => selected.has(id));
        const paramsProfile = group.profiles.find((p) => p.params);
        const pParams = paramsProfile?.params;

        return (
          <li key={group.baseName + "-" + group.ids.join("-")}
            className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel transition hover:shadow-sm">
            {profiles.length > 1 && (
              <input type="checkbox" className="shrink-0 cursor-pointer"
                aria-label={t("profiles.selectRow", { name: group.baseName })}
                checked={isGroupSelected}
                ref={(el) => {
                  if (el) el.indeterminate = isGroupIndeterminate;
                }}
                onChange={() => toggleGroup(group.ids)} />
            )}
            <div className="flex flex-wrap items-center gap-1.5 shrink-0">
              {group.profiles.map((p) => (
                <PortalBadge key={p.id} portal={p.portal} />
              ))}
              {group.profiles.length > 1 && (
                <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border border-purple-200 dark:border-purple-800 shrink-0"
                  title={t("profiles.mergedTitle")}>
                  {t("profiles.merged", { count: group.profiles.length })}
                </span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium text-sm truncate" title={group.baseName}>
                {group.baseName}
              </p>
              {group.profiles.length === 1 ? (
                <p className="text-xs t-dim truncate mt-0.5">
                  <a href={group.profiles[0].search_url} target="_blank" rel="noreferrer" className="hover:underline text-blue-600 dark:text-blue-400">
                    {group.profiles[0].search_url}
                  </a>
                </p>
              ) : (
                <div className="space-y-0.5 mt-1">
                  {group.profiles.map((p) => {
                    const pBadge = statusBadge[p.last_run_status];
                    return (
                      <div key={p.id} className="flex items-center gap-1.5 text-xs t-dim">
                        <span className="font-semibold uppercase text-[10px] w-20 shrink-0 truncate t-muted">
                          {p.portal}:
                        </span>
                        <a href={p.search_url} target="_blank" rel="noreferrer" className="hover:underline truncate min-w-0 flex-1 text-blue-600 dark:text-blue-400" title={p.search_url}>
                          {p.search_url}
                        </a>
                        {pBadge && p.last_run_status !== "ok" && (
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-full shrink-0 ${pBadge.cls}`}>
                            {t(pBadge.label)}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
              {pParams && (pParams.city || pParams.min_price || pParams.max_price || pParams.min_rooms || pParams.min_sqm || pParams.zone) && (
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  {pParams.contract && (
                    <span className="text-[11px] chip-blue px-2 py-0.5 rounded-md font-medium">
                      {t(pParams.contract === "rent" ? "profiles.chipRent" : "profiles.chipBuy")}
                    </span>
                  )}
                  {pParams.city && (
                    <span className="text-[11px] chip-emerald px-2 py-0.5 rounded-md font-medium">
                      📍 {pParams.city}{pParams.province ? ` (${pParams.province})` : ""}
                      {pParams.zone ? ` · ${pParams.zone}` : ""}
                    </span>
                  )}
                  {(pParams.min_price || pParams.max_price) && (
                    <span className="text-[11px] chip-amber px-2 py-0.5 rounded-md font-medium">
                      💰 {pParams.min_price ? `${formatNumber(pParams.min_price)} €` : "0 €"} – {pParams.max_price ? `${formatNumber(pParams.max_price)} €` : "∞"}
                    </span>
                  )}
                  {(pParams.min_rooms || pParams.max_rooms) && (
                    <span className="text-[11px] chip-blue px-2 py-0.5 rounded-md font-medium">
                      {t("profiles.chipRooms", {
                        range: `${pParams.min_rooms ?? 1}${
                          pParams.max_rooms ? `–${pParams.max_rooms}` : "+"
                        }`,
                      })}
                    </span>
                  )}
                  {pParams.min_sqm && (
                    <span className="text-[11px] chip-emerald px-2 py-0.5 rounded-md font-medium">
                      {t("profiles.chipMinSqm", { value: pParams.min_sqm })}
                    </span>
                  )}
                </div>
              )}
              {group.last_run_detail && (
                <p className="text-xs t-muted mt-1">{group.last_run_detail}</p>
              )}
              {combinedKeywords(group.profiles[0], settings).length > 0 && (
                <p className="text-xs t-dim mt-1 truncate"
                  title={t("profiles.excludesTitle")}>
                  {t("profiles.excludes", {
                    words: combinedKeywords(group.profiles[0], settings).join(", "),
                  })}
                </p>
              )}
              {!channel.ok && (
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                  ⚠️ {channel.warn}
                </p>
              )}
            </div>
            {badge && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${badge.cls}`}>
                {t(badge.label)}
                {group.consecutive_failures > 1 && ` ×${group.consecutive_failures}`}
              </span>
            )}
            <select
              className="input !py-1 !px-2 text-xs w-44 shrink-0"
              title={t("profiles.notifyTitle")}
              value={group.notify_channels}
              onChange={(e) => runBulk(group.ids, "notify", e.target.value)}>
              {channelOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer shrink-0">
              <input type="checkbox" checked={group.is_active}
                onChange={() =>
                  runBulk(group.ids, group.is_active ? "pause" : "activate")} />
              {t("profiles.active")}
            </label>
            <div className="flex items-center gap-1 shrink-0">
              <button className="t-dim hover:opacity-70 transition text-sm btn-focus
                  inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
                title={t("profiles.editBox")} aria-label={t("profiles.editBox")}
                onClick={() => editGroup(group)}>
                ✏️
              </button>
              {group.profiles.length > 1 && (
                <button className="t-dim hover:text-purple-500 transition text-sm btn-focus
                    inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
                  title={t("profiles.separateBox")} aria-label={t("profiles.separateBox")}
                  onClick={() => separateGroup(group)}>
                  ✂️
                </button>
              )}
              <button className="t-dim hover:text-rose-500 transition text-sm btn-focus
                  inline-flex items-center justify-center w-8 h-8 rounded-lg shrink-0"
                title={t("profiles.deleteBox")} aria-label={t("profiles.deleteBox")}
                onClick={() => askDelete(group.profiles)}>
                🗑
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
