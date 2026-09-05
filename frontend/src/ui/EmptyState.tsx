/**
 * Nothing here — and what to do about it.
 *
 * An empty region is ambiguous in a way an error never is: the user cannot tell
 * "no results" from "still loading" from "broken" from "you have not set this up
 * yet". So an empty state always says which of those it is, and, where the user
 * can act, hands them the action rather than describing it.
 *
 * `action` is a slot and not an `onClick`, on purpose. The control that appears
 * here is the caller's — it carries the caller's `data-action` id and lands in
 * the inventory in `e2e/actions.ts` under the name of the thing it actually
 * does. A button owned by this file would be one control wearing a different
 * meaning on every screen, which is exactly what the inventory exists to stop.
 *
 * The heading level is a prop because this appears both as a whole page and
 * inside a card, and a heading that is an `h3` in one place and the only heading
 * on the page in the other is how an outline stops being navigable.
 */
import type { ReactNode } from "react";

import { cx } from "./tone";

export interface EmptyStateProps {
  /** Decorative. Rendered `aria-hidden` — the title carries the meaning. */
  icon?: ReactNode;
  title: ReactNode;
  /** Why it is empty, in one sentence. */
  description?: ReactNode;
  /** The way out: a `Button` from this directory, with its own inventory id. */
  action?: ReactNode;
  /** Where this sits in the document outline. */
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

export function EmptyState({
  icon, title, description, action, headingLevel = 3, className,
}: EmptyStateProps) {
  const Heading = `h${headingLevel}` as const;

  return (
    <div className={cx(
      "flex flex-col items-center gap-3 px-6 py-10 text-center",
      className,
    )}>
      {icon && <div aria-hidden="true" className="text-ink-hint">{icon}</div>}
      <Heading className="text-sm font-medium text-ink-strong">{title}</Heading>
      {description && (
        <p className="max-w-sm text-xs leading-relaxed text-ink-muted">{description}</p>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
