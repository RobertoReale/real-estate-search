/**
 * The shape of something that has not arrived yet.
 *
 * A skeleton is not decoration for a spinner: it is a promise about the layout.
 * It occupies the box the real content will occupy, so the page does not jump
 * when the answer lands — which is the actual complaint behind "the app feels
 * slow", more often than the wait itself is.
 *
 * The accessibility question here is not "can it be operated" — nothing can be
 * operated — but "what does a screen reader say about a rectangle". Two
 * answers, and which one is right depends on the caller:
 *
 * - **no `label`**: `aria-hidden`, because the region around it already says
 *   what is loading and a reader announcing four grey boxes adds nothing;
 * - **a `label`**: a live region saying "Loading the listings", for the case
 *   where the skeleton *is* the whole surface and silence would leave the user
 *   with no idea anything is happening.
 */
import { VisuallyHidden } from "radix-ui";

import { cx } from "./tone";

export interface SkeletonProps {
  /** Size and shape, as utilities — `h-4 w-32`, `aspect-[4/3] w-full`. */
  className?: string;
  /** Repeats the block, with the last one short, the way a paragraph ends. */
  lines?: number;
  /** Announce the wait. See the note above for when this is the right call. */
  label?: string;
}

export function Skeleton({ className, lines = 1, label }: SkeletonProps) {
  const blocks = Array.from({ length: Math.max(1, lines) }, (_, index) => (
    <div key={index}
      className={cx(
        "animate-pulse rounded-chip bg-sunken-strong",
        lines > 1 && index === lines - 1 && "w-2/3",
        className,
      )} />
  ));

  if (!label) return <div aria-hidden="true" className="flex flex-col gap-2">{blocks}</div>;

  return (
    <div role="status" aria-busy="true" className="flex flex-col gap-2">
      <VisuallyHidden.Root>{label}</VisuallyHidden.Root>
      <div aria-hidden="true" className="flex flex-col gap-2">{blocks}</div>
    </div>
  );
}
