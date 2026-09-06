/**
 * This region could not be loaded — said where its content would have been.
 *
 * The sibling of `EmptyState`, and the distinction between the two is the whole
 * reason this exists: "nothing matched" and "nobody answered" are the same
 * blank rectangle on screen and they want opposite reactions — one is a filter
 * to loosen, the other is a request to make again. A toast can say a read
 * failed, but a toast leaves, and what it leaves behind is the unexplained
 * empty region it was about.
 *
 * `action` is a slot for the same reason it is one on `EmptyState`: the retry
 * belongs to the surface that failed, carries that surface's `data-action` id,
 * and is inventoried under the name of the thing it actually asks for again.
 */
import type { ReactNode } from "react";

import { EmptyState } from "./EmptyState";
import { ICON_SIZE, Warning } from "./icons";

export interface ErrorStateProps {
  /** What could not be loaded, in the words the screen uses for it. */
  title: ReactNode;
  /** What the backend said about it, when it said anything. */
  description?: ReactNode;
  /** The way out — usually a retry, with its own inventory id. */
  action?: ReactNode;
  /** Where this sits in the document outline. */
  headingLevel?: 2 | 3 | 4;
  className?: string;
}

export function ErrorState({
  title, description, action, headingLevel, className,
}: ErrorStateProps) {
  return (
    // `alert` rather than `status`: this is why the screen is empty, and a
    // reader who has already moved past the region still has to be told.
    <div role="alert">
      <EmptyState headingLevel={headingLevel} className={className}
        icon={(
          <span className="accent-bad">
            <Warning size={ICON_SIZE.display} strokeWidth={1.25} />
          </span>
        )}
        title={title} description={description} action={action} />
    </div>
  );
}
