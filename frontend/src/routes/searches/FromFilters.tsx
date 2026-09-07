/** What the grid's filters became on the way to the portals.
 *
 *  Shown above the form it prefilled, and it is the honest half of the handover:
 *  the form alone would say what carried and say nothing at all about what did
 *  not. A user who filtered by deal score and tag, pressed "Search the portals",
 *  and got a search for a city and a price would have no way of knowing half
 *  their criteria were gone.
 *
 *  The labels come from the grid's own chips, so a criterion is named here in
 *  exactly the words it was named in over there — including its value.
 */
import { useT } from "../../i18n";
import type { TranslationKey } from "../../i18n";
import type { SearchProfile } from "../../types";
import { Card } from "../../ui";
import { activeFilterChips } from "../listings/chips";
import type { Carry, Handoff } from "./handoff";

interface Props {
  handoff: Handoff;
  /** Only to name a "limit to a search" filter by the search it points at. */
  profiles: SearchProfile[];
}

const GROUPS: { carry: Carry; title: TranslationKey }[] = [
  { carry: "exact", title: "handoff.carried" },
  { carry: "approximated", title: "handoff.approximated" },
  { carry: "dropped", title: "handoff.dropped" },
];

export default function FromFilters({ handoff, profiles }: Props) {
  const t = useT();
  const labels = new Map(
    activeFilterChips(handoff.filters, profiles, t).map((chip) => [chip.key, chip.label]),
  );

  return (
    <Card asChild padding="lg">
      <section>
        <h2 className="font-semibold text-base">{t("handoff.title")}</h2>
        <p className="mt-1 text-sm t-muted">{t("handoff.lead")}</p>

        <dl className="mt-3 flex flex-col gap-3">
          {GROUPS.map(({ carry, title }) => {
            const rows = handoff.criteria.filter((c) => c.carry === carry);
            if (rows.length === 0) return null;
            return (
              <div key={carry}>
                <dt className="text-xs font-semibold uppercase tracking-wide t-dim">
                  {t(title)}
                </dt>
                <dd>
                  <ul className="mt-1 flex flex-col gap-1 text-sm">
                    {rows.map(({ key, note }) => {
                      const label = labels.get(key) ?? key;
                      return (
                        // Every dropped or widened criterion is a limit of the
                        // handover, tagged so the sweep in `docs/limits.md` can
                        // point at the line that states it rather than at the
                        // screen it is somewhere on.
                        <li key={key} {...(note ? { "data-limit": `handoff.${key}` } : {})}>
                          {note ? t("handoff.item", { label, note: t(note) }) : label}
                        </li>
                      );
                    })}
                  </ul>
                </dd>
              </div>
            );
          })}
        </dl>
      </section>
    </Card>
  );
}
