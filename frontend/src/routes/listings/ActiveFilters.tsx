/** What the grid is currently narrowed by, above the results, always readable.
 *
 *  One row of chips and the way out of each. It sits between the rail and the
 *  results rather than inside the rail, because its job starts exactly when the
 *  rail's ends: collapsed on a desktop, a sheet on a phone, the rail can be
 *  entirely off screen while the grid is still showing eleven of eighty
 *  properties, and nothing else on the page would say why.
 */
import { useT } from "../../i18n";
import type { PropertyFilters, SearchProfile } from "../../types";
import { Chip } from "../../ui";
import { Close } from "../../ui/icons";
import { activeFilterChips } from "./chips";

interface Props {
  filters: PropertyFilters;
  onChange: (filters: PropertyFilters) => void;
  /** Only to name the "limit to a search" chip after the search it points at. */
  profiles: SearchProfile[];
  /** Clears everything, keeping the Buy/Rent market the user is in. */
  onReset: () => void;
}

export default function ActiveFilters({ filters, onChange, profiles, onReset }: Props) {
  const t = useT();
  const chips = activeFilterChips(filters, profiles, t);

  if (chips.length === 0) return null;

  return (
    <div role="group" aria-label={t("filters.active")}
      className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        // The chip is the label and the button beside it is the control: a
        // `Chip` takes no handler anywhere in this app, so that the tag a
        // listing *has* never looks like a thing to press.
        <Chip key={chip.key} tone="accent" size="md">
          {chip.label}
          <button data-action="filters.chip.remove" type="button"
            className="opacity-60 hover:opacity-100 btn-focus rounded"
            title={t("filters.chipRemove", { label: chip.label })}
            aria-label={t("filters.chipRemove", { label: chip.label })}
            onClick={() => onChange({ ...filters, ...chip.clear })}>
            <Close size={12} />
          </button>
        </Chip>
      ))}
      <button data-action="filters.reset" type="button"
        className="text-xs accent-link hover:underline btn-focus rounded"
        title={t("filters.resetTitle")}
        onClick={onReset}>
        {t("filters.reset")}
      </button>
    </div>
  );
}
