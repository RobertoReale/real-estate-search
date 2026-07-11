import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

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
  const [lines, setLines] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState("");
  const [path, setPath] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.logsTail(500);
        if (cancelled) return;
        setLines(res.lines);
        setPath(res.path);
        setError("");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load logs");
      }
    };
    load();
    if (!autoRefresh) return;
    const timer = setInterval(load, 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [autoRefresh]);

  useEffect(() => {
    if (autoRefresh) bottomRef.current?.scrollIntoView({ block: "end" });
  }, [lines, autoRefresh]);

  const visible = filter
    ? lines.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      <div className="glass rounded-2xl max-w-4xl w-full p-4 sm:p-6 max-h-[90dvh] flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3 gap-3">
          <h2 className="text-lg font-bold shrink-0">📜 Backend log</h2>
          <button className="btn-ghost shrink-0" aria-label="Close" onClick={onClose}>✕</button>
        </div>

        <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 mb-3">
          <input
            type="text"
            placeholder="Filter (e.g. availability_check, blocked, error)"
            className="input col-span-2 w-full sm:w-auto sm:flex-1 sm:min-w-[240px]"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
            <input type="checkbox" checked={autoRefresh}
              onChange={() => setAutoRefresh(!autoRefresh)} />
            Auto-refresh (3s)
          </label>
          <span className="text-xs t-dim ml-auto">{visible.length} / {lines.length} lines</span>
        </div>

        {error && (
          <div className="text-xs text-rose-600 dark:text-rose-400 mb-2">⚠️ {error}</div>
        )}

        <div className="flex-1 min-h-0 overflow-y-auto rounded-xl bg-slate-950 text-slate-200 p-3 font-mono text-[11px] leading-relaxed">
          {visible.length === 0 ? (
            <p className="t-dim">
              {lines.length === 0
                ? "No log lines yet — this fills up once a scan or check runs."
                : "No lines match this filter."}
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
          <p className="text-[10px] t-dim mt-2 truncate">Source: {path}</p>
        )}
      </div>
    </div>
  );
}
