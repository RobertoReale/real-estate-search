import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { useLogTail } from "../queries/maintenance";

interface Props {
  onClose: () => void;
}

const LEVEL_CLASS: Record<string, string> = {
  ERROR: "text-rose-600 dark:text-rose-400",
  WARNING: "text-amber-600 dark:text-amber-400",
};

function levelClass(line: string): string {
  for (const [level, cls] of Object.entries(LEVEL_CLASS)) {
    if (line.includes(` ${level} `)) return cls;
  }
  return "";
}

/** Raw tail of the backend's own app.log: the same file a developer would open
 *  by hand, so "is the scan/check actually doing anything?" has an answer
 *  inside the app instead of requiring a text editor and a file path. */
export default function LogViewer({ onClose }: Props) {
  const t = useT();
  const [filter, setFilter] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  // One key, so one tail is ever in flight: an abandoned request cannot land on
  // top of a newer one, which on a backend slow enough to make anyone open this
  // viewer used to mean the older tail winning.
  const { data, error: failure } = useLogTail(500, autoRefresh);
  const lines = data?.lines ?? [];
  const path = data?.path ?? "";
  const error = failure
    ? (failure instanceof Error ? failure.message : t("logs.loadFailed"))
    : "";

  // On the answer rather than on `lines`: a fresh `[]` fallback every render
  // would scroll on every render, and the tail is what moves the view.
  useEffect(() => {
    if (autoRefresh) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [data, autoRefresh]);

  const visible = filter
    ? lines.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  return (
    <div data-action="logs.close.backdrop" className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      <div data-action="logs.panel" className="glass rounded-2xl max-w-4xl w-full p-4 sm:p-6 max-h-[90dvh] flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3 gap-3">
          <h2 className="text-lg font-bold shrink-0">{t("logs.title")}</h2>
          <button data-action="logs.close" className="btn-ghost shrink-0" aria-label={t("common.close")} onClick={onClose}>✕</button>
        </div>

        <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 mb-3">
          <input data-action="logs.filter"
            type="text"
            placeholder={t("logs.filterPlaceholder")}
            className="input col-span-2 w-full sm:w-auto sm:flex-1 sm:min-w-[240px]"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
            <input data-action="logs.autoRefresh" type="checkbox" checked={autoRefresh}
              onChange={() => setAutoRefresh(!autoRefresh)} />
            {t("logs.autoRefresh")}
          </label>
          <span className="text-xs t-dim ml-auto">
            {t("logs.lineCount", { visible: visible.length, total: lines.length })}
          </span>
        </div>

        {/* Above the empty console rather than in a toast: the failure is why
            there are no lines, and it belongs where the lines would be. */}
        {error && <div className="text-xs t-muted mb-2">{error}</div>}

        <div className="flex-1 min-h-0 overflow-y-auto rounded-xl bg-slate-950 text-slate-200 p-3 font-mono text-[11px] leading-relaxed">
          {visible.length === 0 ? (
            <p className="t-dim">
              {lines.length === 0 ? t("logs.empty") : t("logs.noMatch")}
            </p>
          ) : (
            visible.map((line, i) => (
              <div key={i} className={`whitespace-pre-wrap break-all ${levelClass(line)}`}>
                {line}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {path && (
          <p className="text-[10px] t-dim mt-2 truncate">{t("logs.source", { path })}</p>
        )}
      </div>
    </div>
  );
}
