import { useEffect, useState } from "react";
import type { ScanStatus } from "../types";

interface Props {
  scanStatus: ScanStatus | null;
  onScanNow: () => void;
  onOpenSettings: () => void;
  onOpenLogs: () => void;
}

export default function Navbar({ scanStatus, onScanNow, onOpenSettings, onOpenLogs }: Props) {
  const running = scanStatus?.running ?? false;
  // light is the default; dark only if the user chose it before
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  const nextRun = scanStatus?.next_auto_run
    ? new Date(scanStatus.next_auto_run).toLocaleTimeString([], {
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
            Real Estate Search
          </h1>
          <p className="text-xs t-muted leading-tight hidden sm:block">
            Immobiliare.it + Idealista, without duplicates
          </p>
        </div>
      </div>

      <div className="text-right text-xs t-muted hidden sm:block">
        {running ? (
          <span className="accent-link animate-pulse">⏳ Scan in progress…</span>
        ) : (
          <>
            {scanStatus?.last_summary && <div>{scanStatus.last_summary}</div>}
            {nextRun && <div>Next automatic scan: {nextRun}</div>}
          </>
        )}
      </div>

      <button className="btn-primary shrink-0 px-3 sm:px-4" onClick={onScanNow}
        disabled={running} aria-label="Start scan now">
        {running ? (
          "Running…"
        ) : (
          <>
            <span className="sm:hidden">▶ Scan</span>
            <span className="hidden sm:inline">▶ Start Scan Now</span>
          </>
        )}
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={() => setDark(!dark)}
        title={dark ? "Switch to light theme" : "Switch to dark theme"}
        aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}>
        {dark ? "☀️" : "🌙"}
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={onOpenLogs}
        title="View backend log" aria-label="View backend log">
        📜
      </button>
      <button className="btn-ghost shrink-0 px-3 sm:px-4" onClick={onOpenSettings}
        title="Settings" aria-label="Settings">
        ⚙️
      </button>
    </nav>
  );
}
