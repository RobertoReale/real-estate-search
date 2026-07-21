import { useT } from "../../i18n";
import type { ImportFilters, SearchProfile } from "../../types";
import { groupSearchProfiles } from "../../utils/searchProfiles";


interface Props {
  filters: ImportFilters;
  onFilterChange: (patch: Partial<ImportFilters>) => void;
  profiles: SearchProfile[];
}

export function EmailReviewFilters({ filters, onFilterChange, profiles }: Props) {
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
      <div className="flex flex-col gap-1">
        <label
          className="text-xs t-muted"
          title={t("email.statusTitle")}>
          {t("filters.status")}
        </label>
        <select
          className="input w-full sm:w-40 font-medium"
          value={filters.status}
          onChange={(e) =>
            onFilterChange({
              status: e.target.value as ImportFilters["status"],
            })
          }>
          <option value="pending">{t("email.statusPending")}</option>
          <option value="discarded">{t("email.statusDiscarded")}</option>
          <option value="accepted">{t("email.statusAccepted")}</option>
          <option value="all">{t("email.statusAll")}</option>
        </select>
      </div>
      <div className="col-span-2 flex flex-col gap-1 sm:col-span-1">
        <label
          className="text-xs t-muted"
          title={t("email.filterLikeSearchTitle")}>
          {t("email.filterLikeSearch")}
        </label>
        <select
          className="input w-full sm:w-52"
          value={filters.profile_id}
          onChange={(e) => onFilterChange({ profile_id: e.target.value })}>
          <option value="">{t("email.adHocFilters")}</option>
          {groupSearchProfiles(profiles).map((g) => (
            <option key={g.ids[0]} value={g.ids[0]}>
              {g.baseName} {g.portals.length > 1 ? `(${g.portals.join("/")})` : ""}
            </option>
          ))}
        </select>
      </div>
      {!filters.profile_id && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">{t("email.contract")}</label>
            <select
              className="input w-full sm:w-28"
              value={filters.contract}
              onChange={(e) =>
                onFilterChange({
                  contract: e.target.value as ImportFilters["contract"],
                })
              }>
              <option value="">{t("email.any")}</option>
              <option value="sale">{t("filters.buy")}</option>
              <option value="rent">{t("filters.rent")}</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">{t("filters.city")}</label>
            <input
              className="input w-full sm:w-32"
              placeholder={t("filters.cityPlaceholder")}
              value={filters.city}
              onChange={(e) => onFilterChange({ city: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">{t("filters.minPrice")}</label>
            <input
              className="input w-full sm:w-24"
              type="number"
              value={filters.min_price}
              onChange={(e) => onFilterChange({ min_price: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">{t("filters.maxPrice")}</label>
            <input
              className="input w-full sm:w-24"
              type="number"
              value={filters.max_price}
              onChange={(e) => onFilterChange({ max_price: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">{t("filters.rooms")}</label>
            <select
              className="input w-full sm:w-20"
              value={filters.rooms}
              onChange={(e) => onFilterChange({ rooms: e.target.value })}>
              <option value="">{t("email.any")}</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[10rem]">
            <label className="text-xs t-muted">{t("email.textSearch")}</label>
            <input
              className="input w-full"
              placeholder={t("email.textSearchPlaceholder")}
              value={filters.q}
              onChange={(e) => onFilterChange({ q: e.target.value })}
            />
          </div>
        </>
      )}
    </div>
  );
}
