import type { ReactNode } from "react";

interface Props {
  /** What is progressing, for anyone who cannot see the fill. `children` is the
   *  sentence *beside* the bar, not its name — the two say different things,
   *  and a bar named by its own running commentary is announced afresh on every
   *  tick. */
  label: string;
  done?: number;
  total?: number;
  indeterminate?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * A bar for something that takes a while, in the two shapes an operation can
 * honestly be in.
 *
 * **Only the determinate shape is a `progressbar`.** A fill of `pct` and an
 * `aria-valuenow` are the same claim — "this much of a known whole is done" —
 * and it may only be made where a real total came back. Where none did, this is
 * a pulse and a sentence: no role, no value, no percentage anywhere in the
 * markup. That is deliberately assertable from the outside, and
 * `e2e/activity.spec.ts` asserts it: a portal that declares no page count must
 * produce no `progressbar` on the screen. A bar that fills to 90% and stops
 * teaches the user the app lies, and it is the usual way this kind of screen
 * goes wrong.
 */
export function ProgressBar({
  label,
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
      <div className="h-1.5 w-full rounded-full overflow-hidden bg-sunken-strong">
        {isIndeterminate ? (
          <div className="h-full w-1/3 bg-accent animate-pulse" />
        ) : (
          <div
            role="progressbar"
            aria-label={label}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            className="h-full bg-accent transition-[width] duration-300"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <p className="text-xs t-muted">{children}</p>
    </div>
  );
}
