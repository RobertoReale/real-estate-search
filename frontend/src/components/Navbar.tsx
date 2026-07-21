import { useEffect, useState } from "react";
import { LANGUAGE_NAMES, useI18n } from "../i18n";
import type { ScanStatus } from "../types";

interface Props {
  scanStatus: ScanStatus | null;
  onScanNow: () => void;
  onOpenSettings: () => void;
  onOpenLogs: () => void;
}

export default function Navbar({ scanStatus, onScanNow, onOpenSettings, onOpenLogs }: Props) {
  const { lang, setLang, t } = useI18n();
  const running = scanStatus?.running ?? false;
  // light is the default; dark only if the user chose it before
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // Two languages, so the picker is a toggle like the theme button rather than
  // a dropdown: one tap, and it survives a 390 px navbar.
  const otherLang = lang === "it" ? "en" : "it";
  const switchLangLabel = t("nav.languageSwitchTo", { language: LANGUAGE_NAMES[otherLang] });

  const nextRun = scanStatus?.next_auto_run
    ? new Date(scanStatus.next_auto_run).toLocaleTimeString(lang, {
        hour: "2-digit", minute: "2-digit",
      })
    : null;

  return (
    <nav className="glass sticky top-0 z-40 px-3 sm:px-6 py-3 flex items-center gap-2 sm:gap-4">
      {/* min-w-0 lets the title truncate instead of pushing the buttons off a
          phone screen: the controls are what must survive the narrow layout */}
      <div className="flex items-center gap-2 mr-auto min-w-0">
        <span className="text-2xl">🏠</span>
        <div className="min-w-0">
          <h1 className="font-bold text-base sm:text-lg leading-tight truncate">
            {t("nav.title")}
          </h1>
          <p className="text-xs t-muted leading-tight hidden sm:block">
            {t("nav.subtitle")}
          </p>
        </div>
      </div>

      <div className="text-right text-xs t-muted hidden sm:block">
        {running ? (
          <span className="accent-link animate-pulse">{t("nav.scanning")}</span>
        ) : (
          <>
            {scanStatus?.last_summary && <div>{scanStatus.last_summary}</div>}
            {scanStatus?.paused ? (
              <div className="text-amber-600 dark:text-amber-400">
                {t("nav.paused")}
              </div>
            ) : (
              nextRun && <div>{t("nav.nextScan", { time: nextRun })}</div>
            )}
          </>
        )}
      </div>

      <button className="btn-primary shrink-0 px-3 sm:px-4" onClick={onScanNow}
        disabled={running} aria-label={t("nav.scanNowAria")}>
        {running ? (
          t("nav.running")
        ) : (
          <>
            <span className="sm:hidden">{t("nav.scanNowShort")}</span>
            <span className="hidden sm:inline">{t("nav.scanNow")}</span>
          </>
        )}
      </button>
      <button className="btn-ghost shrink-0 px-2 sm:px-3 font-semibold text-xs"
        onClick={() => setLang(otherLang)}
        title={switchLangLabel} aria-label={switchLangLabel}>
        🌐 {lang.toUpperCase()}
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={() => setDark(!dark)}
        title={dark ? t("nav.toLight") : t("nav.toDark")}
        aria-label={dark ? t("nav.toLight") : t("nav.toDark")}>
        {dark ? "☀️" : "🌙"}
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={onOpenLogs}
        title={t("nav.viewLog")} aria-label={t("nav.viewLog")}>
        📜
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={onOpenSettings}
        title={t("nav.settings")} aria-label={t("nav.settings")}>
        ⚙️
      </button>
    </nav>
  );
}
