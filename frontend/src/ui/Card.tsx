/**
 * A surface that holds a thing: a listing, a panel, a section of a form.
 *
 * It draws the same three utilities `index.css`'s `.glass` does, and does not
 * reuse that class — deliberately. `.glass` belongs to the screens as they are
 * today; this belongs to the screens as they will be after C.4, and a primitive
 * that depends on a legacy class inherits the legacy class's lifetime. The two
 * look identical on purpose so that the migration is invisible while it is half
 * done.
 *
 * `elevation` is a statement about *how far forward* a surface sits, and it is
 * the one place where the two themes are genuinely different mechanisms rather
 * than different numbers: in light, `--shadow-e2` is a cast shadow; in dark, a
 * shadow on a dark ground is invisible, so the same token is a brighter edge.
 * `tokens.css` owns that; a caller only ever names the level.
 */
import { Slot } from "radix-ui";
import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./tone";

const ELEVATIONS = { e1: "shadow-e1", e2: "shadow-e2", e3: "shadow-e3" } as const;

const PADDINGS = { none: "", sm: "p-3", md: "p-4", lg: "p-5 sm:p-6" } as const;

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  elevation?: keyof typeof ELEVATIONS;
  padding?: keyof typeof PADDINGS;
  /** Renders onto the child instead of a `<div>` — an `<article>` for a
   *  listing, an `<li>` in a list, a `<form>` for a panel that submits. */
  asChild?: boolean;
  children?: ReactNode;
}

export function Card({
  elevation = "e1",
  padding = "md",
  asChild = false,
  className,
  ...rest
}: CardProps) {
  const Root = asChild ? Slot.Root : "div";
  return (
    <Root
      className={cx(
        "bg-surface/90 backdrop-blur-xl border border-line rounded-card",
        ELEVATIONS[elevation], PADDINGS[padding], className,
      )}
      {...rest} />
  );
}

/** The line at the top of a card: a title on the left, whatever acts on the
 *  card on the right. Its own component because the alternative is every card
 *  in the app re-deciding the gap and the alignment, which is exactly how the
 *  six button variants happened. */
export function CardHeader({ title, actions, className }: {
  title: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("flex items-start justify-between gap-3", className)}>
      <div className="min-w-0 text-sm font-semibold text-ink-strong">{title}</div>
      {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
    </div>
  );
}
