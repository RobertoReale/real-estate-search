import { useT } from "../../i18n";
import { SectionHeading } from "./controls";
import { splitList, useSectionState, type Section } from "./state";

interface Values {
  enabled: boolean;
  maxPrice: number;
  minRooms: number;
  minSqm: number;
  minFloor: number;
  keywords: string;
  zones: string;
}

export function useMatchSection(): Section<Values> {
  return useSectionState<Values>(
    { enabled: false, maxPrice: 0, minRooms: 0, minSqm: 0, minFloor: 0, keywords: "", zones: "" },
    (s) => ({
      enabled: s.match_score_enabled ?? false,
      maxPrice: s.dream_max_price ?? 0,
      minRooms: s.dream_min_rooms ?? 0,
      minSqm: s.dream_min_sqm ?? 0,
      minFloor: s.dream_min_floor ?? 0,
      keywords: (s.dream_keywords ?? []).join(", "),
      zones: (s.dream_zones ?? []).join(", "),
    }),
    (v) => ({
      match_score_enabled: v.enabled,
      dream_max_price: v.maxPrice,
      dream_min_rooms: v.minRooms,
      dream_min_sqm: v.minSqm,
      dream_min_floor: v.minFloor,
      dream_keywords: splitList(v.keywords),
      dream_zones: splitList(v.zones),
    }),
  );
}

export function MatchSection({ section }: { section: Section<Values> }) {
  const t = useT();
  const { values, set } = section;

  return (
    <>
      <SectionHeading>{t("settings.matchTitle")}</SectionHeading>
      <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
        <input type="checkbox" checked={values.enabled}
          onChange={(e) => set("enabled", e.target.checked)} />
        {t("settings.matchEnable")}
      </label>
      <p className="text-xs t-dim mt-1 mb-2">{t("settings.matchNote")}</p>
      {values.enabled && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <label className="text-xs t-muted col-span-2 sm:col-span-1">
              {t("settings.dreamMaxPrice")}
              <input className="input w-full mt-1" type="number" min={0}
                value={values.maxPrice}
                onChange={(e) => set("maxPrice", Number(e.target.value))} />
            </label>
            <label className="text-xs t-muted">
              {t("settings.dreamMinRooms")}
              <input className="input w-full mt-1" type="number" min={0}
                value={values.minRooms}
                onChange={(e) => set("minRooms", Number(e.target.value))} />
            </label>
            <label className="text-xs t-muted">
              {t("settings.dreamMinSqm")}
              <input className="input w-full mt-1" type="number" min={0}
                value={values.minSqm}
                onChange={(e) => set("minSqm", Number(e.target.value))} />
            </label>
            <label className="text-xs t-muted">
              {t("settings.dreamMinFloor")}
              <input className="input w-full mt-1" type="number" min={0}
                value={values.minFloor}
                onChange={(e) => set("minFloor", Number(e.target.value))} />
            </label>
          </div>
          <div>
            <label className="text-xs t-muted block mb-1" htmlFor="match-features">
              {t("settings.dreamFeatures")}
            </label>
            <input id="match-features" className="input w-full" value={values.keywords}
              onChange={(e) => set("keywords", e.target.value)} />
          </div>
          <div>
            <label className="text-xs t-muted block mb-1" htmlFor="match-zones">
              {t("settings.dreamZones")}
            </label>
            <input id="match-zones" className="input w-full" value={values.zones}
              onChange={(e) => set("zones", e.target.value)} />
          </div>
        </div>
      )}
    </>
  );
}
