import type { ImportFilters, SearchProfile } from "../../types";

interface Props {
  filters: ImportFilters;
  onFilterChange: (patch: Partial<ImportFilters>) => void;
  profiles: SearchProfile[];
}

export function EmailReviewFilters({ filters, onFilterChange, profiles }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
      <div className="flex flex-col gap-1">
        <label
          className="text-xs t-muted"
          title="Scegli se mostrare annunci in attesa, scartati o già accettati">
          Stato / Status
        </label>
        <select
          className="input w-full sm:w-40 font-medium"
          value={filters.status}
          onChange={(e) =>
            onFilterChange({
              status: e.target.value as ImportFilters["status"],
            })
          }>
          <option value="pending">⏳ In attesa (Pending)</option>
          <option value="discarded">🗑️ Scartati (Discarded)</option>
          <option value="accepted">✅ Accettati (Accepted)</option>
          <option value="all">📋 Tutti (All)</option>
        </select>
      </div>
      <div className="col-span-2 flex flex-col gap-1 sm:col-span-1">
        <label
          className="text-xs t-muted"
          title="Reuse the contract, city and excluded keywords of a search you already monitor">
          Filter like search
        </label>
        <select
          className="input w-full sm:w-52"
          value={filters.profile_id}
          onChange={(e) => onFilterChange({ profile_id: e.target.value })}>
          <option value="">— ad-hoc filters —</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      {!filters.profile_id && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Contract</label>
            <select
              className="input w-full sm:w-28"
              value={filters.contract}
              onChange={(e) =>
                onFilterChange({
                  contract: e.target.value as ImportFilters["contract"],
                })
              }>
              <option value="">Any</option>
              <option value="sale">🏠 Buy</option>
              <option value="rent">🔑 Rent</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">City</label>
            <input
              className="input w-full sm:w-32"
              placeholder="e.g. Milano"
              value={filters.city}
              onChange={(e) => onFilterChange({ city: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Min €</label>
            <input
              className="input w-full sm:w-24"
              type="number"
              value={filters.min_price}
              onChange={(e) => onFilterChange({ min_price: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Max €</label>
            <input
              className="input w-full sm:w-24"
              type="number"
              value={filters.max_price}
              onChange={(e) => onFilterChange({ max_price: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs t-muted">Rooms</label>
            <select
              className="input w-full sm:w-20"
              value={filters.rooms}
              onChange={(e) => onFilterChange({ rooms: e.target.value })}>
              <option value="">Any</option>
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[10rem]">
            <label className="text-xs t-muted">Text search</label>
            <input
              className="input w-full"
              placeholder="in title/subject"
              value={filters.q}
              onChange={(e) => onFilterChange({ q: e.target.value })}
            />
          </div>
        </>
      )}
    </div>
  );
}
