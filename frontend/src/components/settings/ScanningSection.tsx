import { useT } from "../../i18n";
import { SectionHeading } from "./controls";
import { splitList, useSectionState, type Section } from "./state";

interface Values {
  interval: number;
  paused: boolean;
  healthAfter: number;
  keywords: string;
}

export function useScanningSection(): Section<Values> {
  return useSectionState<Values>(
    { interval: 60, paused: false, healthAfter: 3, keywords: "" },
    (s) => ({
      interval: s.scan_interval_minutes,
      paused: s.scanning_paused ?? false,
      healthAfter: s.health_alert_after_failures,
      keywords: s.excluded_keywords.join(", "),
    }),
    (v) => ({
      scan_interval_minutes: v.interval,
      scanning_paused: v.paused,
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
      <SectionHeading>{t("settings.scanTitle")}</SectionHeading>
      <label className="text-xs t-muted" htmlFor="scan-interval">{t("settings.frequency")}</label>
      <select id="scan-interval" className="input w-full mt-1" value={values.interval}
        onChange={(e) => set("interval", Number(e.target.value))}>
        <option value={30}>{t("settings.every30m")}</option>
        <option value={60}>{t("settings.everyHour")}</option>
        <option value={120}>{t("settings.every2h")}</option>
        <option value={240}>{t("settings.every4h")}</option>
        <option value={480}>{t("settings.every8h")}</option>
      </select>

      <label className="flex items-start gap-2 mt-3 cursor-pointer">
        <input type="checkbox" checked={values.paused} className="mt-0.5"
          onChange={(e) => set("paused", e.target.checked)} />
        <span className="text-sm">
          {t("settings.pauseScans")}
          <span className="block text-xs t-dim">{t("settings.pauseScansNote")}</span>
        </span>
      </label>

      <SectionHeading>{t("settings.healthTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.healthNote")}</p>
      <label className="text-xs t-muted" htmlFor="health-after">
        {t("settings.alertAfter")}
      </label>
      <select id="health-after" className="input w-full mt-1" value={values.healthAfter}
        onChange={(e) => set("healthAfter", Number(e.target.value))}>
        <option value={0}>{t("settings.neverDisabled")}</option>
        {[2, 3, 5, 10].map((n) => (
          <option key={n} value={n}>{t("settings.nFailures", { count: n })}</option>
        ))}
      </select>

      <SectionHeading>{t("settings.keywordsTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.keywordsNote")}</p>
      <textarea className="input w-full h-20 resize-none"
        aria-label={t("settings.keywordsTitle")}
        value={values.keywords} onChange={(e) => set("keywords", e.target.value)} />
    </>
  );
}
