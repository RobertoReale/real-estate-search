/** The results region while the first answer is still on its way.
 *
 *  It exists because the alternative is a lie. With nothing loaded yet the
 *  column had exactly one fallback — `EmptyResults` — so a grid that had not
 *  answered was indistinguishable from one that had answered "nothing matches",
 *  and the screen told a user to relax filters that had not yet been applied to
 *  anything. A shape where the cards will be says the only true thing there is
 *  to say at that moment: this is coming.
 *
 *  It mirrors the grid's own columns rather than showing one generic bar, so
 *  the layout does not jump when the real cards land in it.
 */
import { useT } from "../../i18n";
import type { ViewMode } from "../../types";
import { Card, Skeleton } from "../../ui";

/** Two rows at the widest breakpoint, one at most others. Enough to read as
 *  "results are coming", not so many that a fast answer flashes a full page of
 *  grey. */
const PLACEHOLDERS = 8;

export default function ResultsPending({ view }: { view: ViewMode }) {
  const t = useT();

  // The map is one region, not a set of cards, and a grid of card shapes in
  // front of it would be a promise about the wrong thing.
  if (view === "map") {
    return <Skeleton className="h-[60vh] w-full rounded-2xl" label={t("app.loadingResults")} />;
  }

  return (
    <div className="grid gap-4 sm:gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: PLACEHOLDERS }, (_, index) => (
        <Card key={index} padding="none" className="overflow-hidden">
          {/* Announced once for the whole region: eight live regions saying
              "loading" is eight interruptions for one wait. */}
          <Skeleton className="aspect-[4/3] w-full rounded-none"
            label={index === 0 ? t("app.loadingResults") : undefined} />
          <div className="p-3 sm:p-4">
            <Skeleton className="h-3" lines={3} />
          </div>
        </Card>
      ))}
    </div>
  );
}
