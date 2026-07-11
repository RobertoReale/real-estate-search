import type { ReactNode } from "react";

interface Props {
  done?: number;
  total?: number;
  indeterminate?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Accessible, responsive progress bar for asynchronous operations.
 * Displays percentage progress or an indeterminate pulse indicator along with live status text.
 */
export function ProgressBar({
  done = 0,
  total = 0,
  indeterminate = false,
  className = "",
  children,
}: Props) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const isIndeterminate = indeterminate || total <= 0;

  return (
    <div className={`space-y-1.5 ${className}`} role="status" aria-live="polite">
      <div className="h-1.5 w-full rounded-full overflow-hidden bg-slate-200 dark:bg-slate-700">
        {isIndeterminate ? (
          <div className="h-full w-1/3 bg-blue-500 animate-pulse" />
        ) : (
          <div
            className="h-full bg-blue-500 transition-[width] duration-300"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <p className="text-xs t-muted">{children}</p>
    </div>
  );
}
