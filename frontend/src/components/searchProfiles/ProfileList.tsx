/** The monitored searches themselves, one row per group (a "group" being the
 * same search on both portals, folded into one card). */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { formatNumber } from "../../i18n";
import { PortalBadge } from "../PortalBadge";
import { statusBadge } from "./constants";
import { combinedKeywords } from "./helpers";
import { Checkbox, Chip, IconButton } from "../../ui";
import { Area, Delete, Edit, Filtered, Place, Price, Rooms, Split } from "../../ui/icons";

export function ProfileList({ sp }: { sp: SearchProfilesState }) {
  const { t, settings, profiles, groupedProfiles, selected, toggleGroup, channelOptions,
    runBulk, editGroup, separateGroup, askDelete } = sp;
  return (
    <ul className="space-y-2">
      {groupedProfiles.map((group) => {
        const badge = statusBadge[group.last_run_status];
        const isGroupSelected = group.ids.length > 0 && group.ids.every((id) => selected.has(id));
        const isGroupIndeterminate = !isGroupSelected && group.ids.some((id) => selected.has(id));
        const paramsProfile = group.profiles.find((p) => p.params);
        const pParams = paramsProfile?.params;

        return (
          // One wrapping row, but the wrapping is declared rather than left to
          // chance: the name/URL block and the notify select each claim the
          // full width on a phone, which puts the identity of the search on its
          // own line and the controls on theirs. Squeezed into one row at 390px
          // this was unreadable rather than merely tight — the name clipped to
          // "Trilo…", the URL to "https:…", and the row pushed the document
          // sideways. From `sm` up every block returns to its share of the row.
          <li key={group.baseName + "-" + group.ids.join("-")}
            className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel transition hover:shadow-sm">
            {profiles.length > 1 && (
              <input data-action="profiles.row.select" type="checkbox" className="shrink-0 cursor-pointer"
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
                <span title={t("profiles.mergedTitle")}>
                  <Chip tone="tag" className="shrink-0">
                    {t("profiles.merged", { count: group.profiles.length })}
                  </Chip>
                </span>
              )}
            </div>
            <div className="w-full min-w-0 sm:w-auto sm:flex-1">
              <p className="font-medium text-sm truncate" title={group.baseName}>
                {group.baseName}
              </p>
              {group.profiles.length === 1 ? (
                <p className="text-xs t-dim truncate mt-0.5">
                  <a href={group.profiles[0].search_url} target="_blank" rel="noreferrer" className="hover:underline text-accent-link">
                    {group.profiles[0].search_url}
                  </a>
                </p>
              ) : (
                <div className="space-y-0.5 mt-1">
                  {group.profiles.map((p) => {
                    const pBadge = statusBadge[p.last_run_status];
                    return (
                      <div key={p.id} className="flex items-center gap-1.5 text-xs t-dim">
                        <span className="font-semibold uppercase text-3xs w-20 shrink-0 truncate t-muted">
                          {p.portal}:
                        </span>
                        <a href={p.search_url} target="_blank" rel="noreferrer" className="hover:underline truncate min-w-0 flex-1 text-accent-link" title={p.search_url}>
                          {p.search_url}
                        </a>
                        {pBadge && p.last_run_status !== "ok" && (
                          <span className={`text-3xs px-1.5 py-0.2 rounded-full shrink-0 ${pBadge.cls}`}>
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
                    <Chip tone="accent">
                      {t(pParams.contract === "rent" ? "profiles.chipRent" : "profiles.chipBuy")}
                    </Chip>
                  )}
                  {pParams.city && (
                    <Chip tone="positive">
                      <Place /> {pParams.city}{pParams.province ? ` (${pParams.province})` : ""}
                      {pParams.zone ? ` · ${pParams.zone}` : ""}
                    </Chip>
                  )}
                  {(pParams.min_price || pParams.max_price) && (
                    <Chip tone="caution">
                      <Price /> {pParams.min_price ? `${formatNumber(pParams.min_price)} €` : "0 €"} – {pParams.max_price ? `${formatNumber(pParams.max_price)} €` : "∞"}
                    </Chip>
                  )}
                  {(pParams.min_rooms || pParams.max_rooms) && (
                    <Chip tone="accent">
                      <Rooms />{" "}
                      {t("profiles.chipRooms", {
                        range: `${pParams.min_rooms ?? 1}${
                          pParams.max_rooms ? `–${pParams.max_rooms}` : "+"
                        }`,
                      })}
                    </Chip>
                  )}
                  {pParams.min_sqm && (
                    <Chip tone="positive">
                      <Area /> {t("profiles.chipMinSqm", { value: pParams.min_sqm })}
                    </Chip>
                  )}
                </div>
              )}
              {group.last_run_detail && (
                <p className="text-xs t-muted mt-1">{group.last_run_detail}</p>
              )}
              {combinedKeywords(group.profiles[0], settings).length > 0 && (
                <p className="flex items-center gap-1 text-xs t-dim mt-1 truncate"
                  title={t("profiles.excludesTitle")}>
                  <Filtered className="shrink-0" />
                  {t("profiles.excludes", {
                    words: combinedKeywords(group.profiles[0], settings).join(", "),
                  })}
                </p>
              )}
            </div>
            {badge && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${badge.cls}`}>
                {t(badge.label)}
                {group.consecutive_failures > 1 && ` ×${group.consecutive_failures}`}
              </span>
            )}
            <select data-action="profiles.row.notify"
              className="input !py-1 !px-2 text-xs min-w-0 flex-1 sm:flex-none sm:w-44"
              // A `title` alone is not a label: it never reaches a touch user
              // and a screen reader may or may not announce it, so the control
              // that decides where a search's alerts go was unnamed.
              aria-label={t("profiles.notifyFor", { name: group.baseName })}
              title={t("profiles.notifyTitle")}
              value={group.notify_channels}
              onChange={(e) => runBulk(group.ids, "notify", e.target.value)}>
              {channelOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <Checkbox data-action="profiles.row.active"
              className="shrink-0"
              checked={group.is_active}
              onCheckedChange={() =>
                runBulk(group.ids, group.is_active ? "pause" : "activate")}
              label={t("profiles.active")} />
            <div className="flex items-center gap-1 shrink-0">
              <IconButton data-action="profiles.row.edit" variant="ghost" size="sm" className="shrink-0"
                label={t("profiles.editBox")} onClick={() => editGroup(group)}>
                <Edit size={16} />
              </IconButton>
              {group.profiles.length > 1 && (
                <IconButton data-action="profiles.row.separate" variant="ghost" size="sm" className="shrink-0"
                  label={t("profiles.separateBox")} onClick={() => separateGroup(group)}>
                  <Split size={16} />
                </IconButton>
              )}
              <IconButton data-action="profiles.row.delete" variant="ghost" tone="negative" size="sm"
                className="shrink-0" label={t("profiles.deleteBox")}
                onClick={() => askDelete(group.profiles)}>
                <Delete size={16} />
              </IconButton>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
