import { useT } from "../../i18n";
import { useComputeCommutes } from "../../queries/maintenance";
import type { CommuteMode, CommutePoint, CommuteSummary, Settings } from "../../types";
import { Result, SectionHeading } from "./controls";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  enabled: boolean;
  osrmUrl: string;
  points: CommutePoint[];
}

const MODES: CommuteMode[] = ["car", "foot", "bike"];

/** A blank row, so "Add a place" gives the user something to type into rather
 *  than a second button to press first. The coordinates are explicitly null:
 *  a new place has an address to be resolved, not a pin, and the backend sends
 *  every one of these five keys on the way back. */
const EMPTY: CommutePoint = { name: "", address: "", lat: null, lng: null, mode: "car" };

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
  const compute = useComputeCommutes();

  function update(index: number, patch: Partial<CommutePoint>) {
    set("points", values.points.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  return (
    <>
      <SectionHeading>{t("settings.commuteTitle")}</SectionHeading>
      <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
        <input data-action="settings.commute.enable" type="checkbox" checked={values.enabled}
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
                <input data-action="settings.commute.pointName" className="input w-full sm:w-32 mt-1" value={point.name}
                  placeholder={t("settings.commutePointNamePlaceholder")}
                  onChange={(e) => update(i, { name: e.target.value })} />
              </label>
              <label className="text-xs t-muted col-span-2 sm:flex-1">
                {t("settings.commutePointAddress")}
                <input data-action="settings.commute.pointAddress" className="input w-full mt-1" value={point.address ?? ""}
                  placeholder={t("settings.commutePointAddressPlaceholder")}
                  onChange={(e) => update(i, { address: e.target.value })} />
              </label>
              <label className="text-xs t-muted">
                {t("settings.commutePointMode")}
                <select data-action="settings.commute.pointMode" className="input w-full sm:w-28 mt-1" value={point.mode}
                  onChange={(e) => update(i, { mode: e.target.value as CommuteMode })}>
                  {MODES.map((m) => <option key={m} value={m}>{t(`settings.commuteMode.${m}`)}</option>)}
                </select>
              </label>
              <button data-action="settings.commute.removePoint" className="btn-ghost" aria-label={t("settings.commuteRemovePoint")}
                onClick={() => set("points", values.points.filter((_, j) => j !== i))}>
                🗑
              </button>
            </div>
          ))}

          <button data-action="settings.commute.addPoint" className="btn-ghost text-xs"
            onClick={() => set("points", [...values.points, { ...EMPTY }])}>
            ＋ {t("settings.commuteAddPoint")}
          </button>

          <div>
            <label className="text-xs t-muted block mb-1" htmlFor="commute-osrm-url">{t("settings.commuteOsrmUrl")}</label>
            <input data-action="settings.commute.osrmUrl" id="commute-osrm-url" className="input w-full" value={values.osrmUrl}
              placeholder="https://router.project-osrm.org"
              onChange={(e) => set("osrmUrl", e.target.value)} />
            <p className="text-xs t-dim mt-1">{t("settings.commuteOsrmNote")}</p>
          </div>

          {/* The grid only reads already-routed legs, so nothing appears on a
              card until this has run at least once. Through saveAndTest, so the
              batch routes to the places just typed rather than the saved ones. */}
          <button data-action="settings.commute.compute" className="btn-primary w-full sm:w-auto" disabled={shell.anyBusy}
            onClick={() => shell.saveAndTest(
              "commute",
              () => compute.mutateAsync(),
              (r) => {
                const s = r as CommuteSummary;
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
