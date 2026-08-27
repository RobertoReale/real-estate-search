import { useT } from "../../i18n";
import { api } from "../../services/api";
import type { CommuteMode, CommutePoint, Settings } from "../../types";
import { Result, SectionHeading } from "./controls";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  enabled: boolean;
  osrmUrl: string;
  points: CommutePoint[];
}

const MODES: CommuteMode[] = ["car", "foot", "bike"];

/** A blank row, so "Add a place" gives the user something to type into rather
 *  than a second button to press first. */
const EMPTY: CommutePoint = { name: "", address: "", mode: "car" };

export function useCommuteSection(): Section<Values> {
  return useSectionState<Values>(
    { enabled: false, osrmUrl: "", points: [] },
    (s) => ({
      enabled: s.commute_enabled ?? false,
      osrmUrl: s.osrm_url ?? "",
      points: (s.commute_points ?? []).map((p) => ({ ...p })),
    }),
    (v) => ({
      commute_enabled: v.enabled,
      osrm_url: v.osrmUrl,
      // Drop the blank rows the "Add a place" button leaves behind, but keep
      // any lat/lng a point already carries: the form only edits the name,
      // the address and the mode, and silently dropping a resolved pin would
      // make the next batch re-geocode it for nothing.
      commute_points: v.points.filter((p) => p.name.trim() && (p.address?.trim() || p.lat != null)),
    }),
  );
}

export function CommuteSection(
  { section, settings, shell }: { section: Section<Values>; settings: Settings; shell: SettingsShell },
) {
  const t = useT();
  const { values, set } = section;

  function update(index: number, patch: Partial<CommutePoint>) {
    set("points", values.points.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  return (
    <>
      <SectionHeading>{t("settings.commuteTitle")}</SectionHeading>
      <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
        <input type="checkbox" checked={values.enabled}
          onChange={(e) => set("enabled", e.target.checked)} />
        {t("settings.commuteEnable")}
      </label>
      <p className="text-xs t-dim mt-1 mb-2">{t("settings.commuteNote")}</p>

      {values.enabled && (
        <div className="space-y-3">
          {values.points.map((point, i) => (
            <div key={i} className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 items-end">
              <label className="text-xs t-muted">
                {t("settings.commutePointName")}
                <input className="input w-full sm:w-32 mt-1" value={point.name}
                  placeholder={t("settings.commutePointNamePlaceholder")}
                  onChange={(e) => update(i, { name: e.target.value })} />
              </label>
              <label className="text-xs t-muted col-span-2 sm:flex-1">
                {t("settings.commutePointAddress")}
                <input className="input w-full mt-1" value={point.address ?? ""}
                  placeholder={t("settings.commutePointAddressPlaceholder")}
                  onChange={(e) => update(i, { address: e.target.value })} />
              </label>
              <label className="text-xs t-muted">
                {t("settings.commutePointMode")}
                <select className="input w-full sm:w-28 mt-1" value={point.mode}
                  onChange={(e) => update(i, { mode: e.target.value as CommuteMode })}>
                  {MODES.map((m) => <option key={m} value={m}>{t(`settings.commuteMode.${m}`)}</option>)}
                </select>
              </label>
              <button className="btn-ghost" aria-label={t("settings.commuteRemovePoint")}
                onClick={() => set("points", values.points.filter((_, j) => j !== i))}>
                🗑
              </button>
            </div>
          ))}

          <button className="btn-ghost text-xs"
            onClick={() => set("points", [...values.points, { ...EMPTY }])}>
            ＋ {t("settings.commuteAddPoint")}
          </button>

          <div>
            <label className="text-xs t-muted block mb-1">{t("settings.commuteOsrmUrl")}</label>
            <input className="input w-full" value={values.osrmUrl}
              placeholder="https://router.project-osrm.org"
              onChange={(e) => set("osrmUrl", e.target.value)} />
            <p className="text-xs t-dim mt-1">{t("settings.commuteOsrmNote")}</p>
          </div>

          {/* The grid only reads already-routed legs, so nothing appears on a
              card until this has run at least once. Through saveAndTest, so the
              batch routes to the places just typed rather than the saved ones. */}
          <button className="btn-primary w-full sm:w-auto" disabled={shell.anyBusy}
            onClick={() => shell.saveAndTest(
              "commute",
              () => api.computeCommutes(),
              (r) => {
                const s = r as Awaited<ReturnType<typeof api.computeCommutes>>;
                return t("settings.commuteComputed", {
                  routed: s.routed, scanned: s.scanned,
                }) + (s.remaining > 0 ? t("settings.commuteRemaining", { count: s.remaining }) : "");
              },
            )}>
            {shell.busy === "commute" ? t("settings.commuteComputing") : t("settings.commuteCompute")}
          </button>
          <p className="text-xs t-dim">
            {t("settings.commuteComputeNote", {
              url: settings.osrm_url || "https://router.project-osrm.org",
            })}
          </p>
          <Result feedback={shell.feedback} where="commute" />
        </div>
      )}
    </>
  );
}
