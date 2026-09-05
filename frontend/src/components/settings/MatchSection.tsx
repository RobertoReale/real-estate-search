import { useT } from "../../i18n";
import { SectionHeading } from "./controls";
import { Checkbox, Field, Input } from "../../ui";
import { Deal } from "../../ui/icons";
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
      <SectionHeading icon={Deal}>{t("settings.matchTitle")}</SectionHeading>
      <Checkbox data-action="settings.match.enable" label={t("settings.matchEnable")}
        checked={values.enabled} onCheckedChange={(v) => set("enabled", v === true)} />
      <p className="text-xs t-dim mt-1 mb-2">{t("settings.matchNote")}</p>
      {values.enabled && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Field label={t("settings.dreamMaxPrice")} className="col-span-2 sm:col-span-1">
              <Input data-action="settings.match.maxPrice" type="number" min={0}
                value={values.maxPrice}
                onChange={(e) => set("maxPrice", Number(e.target.value))} />
            </Field>
            <Field label={t("settings.dreamMinRooms")}>
              <Input data-action="settings.match.minRooms" type="number" min={0}
                value={values.minRooms}
                onChange={(e) => set("minRooms", Number(e.target.value))} />
            </Field>
            <Field label={t("settings.dreamMinSqm")}>
              <Input data-action="settings.match.minSqm" type="number" min={0}
                value={values.minSqm}
                onChange={(e) => set("minSqm", Number(e.target.value))} />
            </Field>
            <Field label={t("settings.dreamMinFloor")}>
              <Input data-action="settings.match.minFloor" type="number" min={0}
                value={values.minFloor}
                onChange={(e) => set("minFloor", Number(e.target.value))} />
            </Field>
          </div>
          <Field label={t("settings.dreamFeatures")}>
            <Input data-action="settings.match.features" value={values.keywords}
              onChange={(e) => set("keywords", e.target.value)} />
          </Field>
          <Field label={t("settings.dreamZones")}>
            <Input data-action="settings.match.zones" value={values.zones}
              onChange={(e) => set("zones", e.target.value)} />
          </Field>
        </div>
      )}
    </>
  );
}
