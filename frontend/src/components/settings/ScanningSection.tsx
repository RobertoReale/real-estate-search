import { useT } from "../../i18n";
import { SectionHeading } from "./controls";
import { Checkbox, Textarea } from "../../ui";
import { Alarm, Filtered, Restart } from "../../ui/icons";
import { splitList, useSectionState, type Section } from "./state";

interface Values {
  interval: number;
  paused: boolean;
  goneAfter: number;
  notifyCap: number;
  healthAfter: number;
  keywords: string;
}

/** Days unseen before a listing is called gone. The threshold is in days rather
 *  than "missing from the last scan" so a run of 403s cannot empty the grid,
 *  which is why the shortest offer is still measured in days. */
const GONE_AFTER_DAYS = [2, 3, 5, 7, 14, 30];
const NOTIFY_CAPS = [5, 10, 15, 25, 50];

export function useScanningSection(): Section<Values> {
  return useSectionState<Values>(
    { interval: 60, paused: false, goneAfter: 7, notifyCap: 15, healthAfter: 3, keywords: "" },
    (s) => ({
      interval: s.scan_interval_minutes,
      paused: s.scanning_paused ?? false,
      goneAfter: s.gone_after_days,
      notifyCap: s.max_notifications_per_scan,
      healthAfter: s.health_alert_after_failures,
      keywords: s.excluded_keywords.join(", "),
    }),
    (v) => ({
      scan_interval_minutes: v.interval,
      scanning_paused: v.paused,
      gone_after_days: v.goneAfter,
      max_notifications_per_scan: v.notifyCap,
      health_alert_after_failures: v.healthAfter,
      excluded_keywords: splitList(v.keywords),
    }),
  );
}

export function ScanningSection({ section }: { section: Section<Values> }) {
  const t = useT();
  const { values, set } = section;

  return (
    <>
      <SectionHeading icon={Restart}>{t("settings.scanTitle")}</SectionHeading>
      <label className="text-xs t-muted" htmlFor="scan-interval">{t("settings.frequency")}</label>
      <select data-action="settings.scanning.interval" id="scan-interval" className="input w-full mt-1" value={values.interval}
        onChange={(e) => set("interval", Number(e.target.value))}>
        <option value={30}>{t("settings.every30m")}</option>
        <option value={60}>{t("settings.everyHour")}</option>
        <option value={120}>{t("settings.every2h")}</option>
        <option value={240}>{t("settings.every4h")}</option>
        <option value={480}>{t("settings.every8h")}</option>
      </select>

      <Checkbox data-action="settings.scanning.pause" className="mt-3"
        checked={values.paused} onCheckedChange={(v) => set("paused", v === true)}
        label={<>
          {t("settings.pauseScans")}
          <span className="block text-xs t-dim">{t("settings.pauseScansNote")}</span>
        </>} />

      <label className="text-xs t-muted block mt-3" htmlFor="gone-after">
        {t("settings.goneAfter")}
      </label>
      <select data-action="settings.scanning.goneAfter" id="gone-after" className="input w-full mt-1"
        value={values.goneAfter} onChange={(e) => set("goneAfter", Number(e.target.value))}>
        {GONE_AFTER_DAYS.map((n) => (
          <option key={n} value={n}>{t("settings.nDays", { count: n })}</option>
        ))}
      </select>
      <p className="text-xs t-dim mt-1">{t("settings.goneAfterNote")}</p>

      <label className="text-xs t-muted block mt-3" htmlFor="notify-cap">
        {t("settings.notifyCap")}
      </label>
      <select data-action="settings.scanning.notifyCap" id="notify-cap" className="input w-full mt-1"
        value={values.notifyCap} onChange={(e) => set("notifyCap", Number(e.target.value))}>
        {NOTIFY_CAPS.map((n) => (
          <option key={n} value={n}>{t("settings.nNotifications", { count: n })}</option>
        ))}
      </select>
      <p className="text-xs t-dim mt-1">{t("settings.notifyCapNote")}</p>

      <SectionHeading icon={Alarm}>{t("settings.healthTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.healthNote")}</p>
      <label className="text-xs t-muted" htmlFor="health-after">
        {t("settings.alertAfter")}
      </label>
      <select data-action="settings.scanning.healthAfter" id="health-after" className="input w-full mt-1" value={values.healthAfter}
        onChange={(e) => set("healthAfter", Number(e.target.value))}>
        <option value={0}>{t("settings.neverDisabled")}</option>
        {[2, 3, 5, 10].map((n) => (
          <option key={n} value={n}>{t("settings.nFailures", { count: n })}</option>
        ))}
      </select>

      <SectionHeading icon={Filtered}>{t("settings.keywordsTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.keywordsNote")}</p>
      <Textarea data-action="settings.scanning.keywords" className="h-20"
        aria-label={t("settings.keywordsTitle")}
        value={values.keywords} onChange={(e) => set("keywords", e.target.value)} />
    </>
  );
}
