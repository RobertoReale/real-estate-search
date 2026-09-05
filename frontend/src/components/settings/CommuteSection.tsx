import { useT } from "../../i18n";
import { useComputeCommutes } from "../../queries/maintenance";
import type { CommuteMode, CommutePoint, CommuteSummary, Settings } from "../../types";
import { Result, SectionHeading } from "./controls";
import { Button, Checkbox, Field, IconButton, Input } from "../../ui";
import { Add, Commute, Delete } from "../../ui/icons";
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
      <SectionHeading icon={Commute}>{t("settings.commuteTitle")}</SectionHeading>
      <Checkbox data-action="settings.commute.enable" label={t("settings.commuteEnable")}
        checked={values.enabled} onCheckedChange={(v) => set("enabled", v === true)} />
      <p className="text-xs t-dim mt-1 mb-2">{t("settings.commuteNote")}</p>

      {values.enabled && (
        <div className="space-y-3">
          {values.points.map((point, i) => (
            <div key={i} className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 items-end">
              <Field label={t("settings.commutePointName")}>
                <Input data-action="settings.commute.pointName" className="sm:w-32" value={point.name}
                  placeholder={t("settings.commutePointNamePlaceholder")}
                  onChange={(e) => update(i, { name: e.target.value })} />
              </Field>
              <Field label={t("settings.commutePointAddress")} className="col-span-2 sm:flex-1">
                <Input data-action="settings.commute.pointAddress" value={point.address ?? ""}
                  placeholder={t("settings.commutePointAddressPlaceholder")}
                  onChange={(e) => update(i, { address: e.target.value })} />
              </Field>
              <label className="text-xs t-muted">
                {t("settings.commutePointMode")}
                <select data-action="settings.commute.pointMode" className="input w-full sm:w-28 mt-1" value={point.mode}
                  onChange={(e) => update(i, { mode: e.target.value as CommuteMode })}>
                  {MODES.map((m) => <option key={m} value={m}>{t(`settings.commuteMode.${m}`)}</option>)}
                </select>
              </label>
              <IconButton data-action="settings.commute.removePoint" label={t("settings.commuteRemovePoint")}
                onClick={() => set("points", values.points.filter((_, j) => j !== i))}>
                <Delete size={16} />
              </IconButton>
            </div>
          ))}

          <Button data-action="settings.commute.addPoint" size="sm"
            onClick={() => set("points", [...values.points, { ...EMPTY }])}>
            <Add /> {t("settings.commuteAddPoint")}
          </Button>

          <Field label={t("settings.commuteOsrmUrl")} hint={t("settings.commuteOsrmNote")}>
            <Input data-action="settings.commute.osrmUrl" value={values.osrmUrl}
              placeholder="https://router.project-osrm.org"
              onChange={(e) => set("osrmUrl", e.target.value)} />
          </Field>

          {/* The grid only reads already-routed legs, so nothing appears on a
              card until this has run at least once. Through saveAndTest, so the
              batch routes to the places just typed rather than the saved ones. */}
          <Button data-action="settings.commute.compute" variant="solid" tone="accent"
            className="w-full sm:w-auto" disabled={shell.anyBusy}
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
          </Button>
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
