import { formatPrice } from "../../services/api";
import type { ImportedListing } from "../../types";
import { PortalBadge } from "../PortalBadge";

/**
 * Calculates price per square meter from the email import data.
 */
export function pricePerSqm(item: ImportedListing): number | null {
  if (!item.price || !item.sqm) return null;
  return Math.round(item.price / item.sqm);
}

export function formatSqmPrice(item: ImportedListing): string {
  const value = pricePerSqm(item);
  if (value === null) return "";
  return item.contract === "rent"
    ? `${value.toLocaleString("it-IT")} €/m² per month`
    : `${value.toLocaleString("it-IT")} €/m²`;
}

interface Props {
  item: ImportedListing;
  selected: boolean;
  onToggleSelect: () => void;
  onAccept: () => void;
  onDiscard: () => void;
  busy: boolean;
}

export function EmailListingCard({
  item,
  selected,
  onToggleSelect,
  onAccept,
  onDiscard,
  busy,
}: Props) {
  const sqmPriceStr = formatSqmPrice(item);

  return (
    <li className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel">
      <input type="checkbox" checked={selected} onChange={onToggleSelect} />
      <PortalBadge portal={item.portal} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="font-medium text-sm truncate">
            {item.title || item.email_subject || `Listing ${item.portal_id}`}
          </p>
          {item.status && item.status !== "pending" && (
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded shrink-0 ${
                item.status === "accepted"
                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                  : "bg-rose-500/20 text-rose-600 dark:text-rose-400"
              }`}>
              {item.status === "accepted" ? "✅ Accettato" : "🗑️ Scartato"}
            </span>
          )}
        </div>
        {item.is_available === false && (
          <p className="text-xs text-rose-600 dark:text-rose-400">
            🚫 No longer online — the portal answered "page not found"
          </p>
        )}
        <p className="text-xs t-dim truncate">
          {[
            formatPrice(item.price, item.contract),
            item.sqm ? `${item.sqm} m²` : "",
            item.rooms ? `${item.rooms} rooms` : "",
            item.contract === "rent" ? "rent" : "sale",
            item.email_date
              ? `email of ${new Date(item.email_date).toLocaleDateString()}`
              : "",
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {item.title && item.email_subject && (
          <p
            className="text-xs t-dim truncate opacity-70"
            title={`${item.email_subject} — from ${item.email_from}`}>
            ✉️ {item.email_subject}
          </p>
        )}
      </div>
      {sqmPriceStr && (
        <span
          className="text-xs font-medium shrink-0 px-2 py-1 rounded-lg bg-slate-500/10"
          title="Price divided by surface — the only comparable figure the email provides">
          {sqmPriceStr}
        </span>
      )}
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        className="accent-link text-xs shrink-0"
        title="The ad may no longer exist on the portal">
        Open ↗
      </a>
      {item.status !== "accepted" && (
        <button
          className="btn-ghost text-xs"
          disabled={busy}
          title="Add to the dashboard (deduplicated against existing properties)"
          onClick={onAccept}>
          ✓ {item.status === "discarded" ? "Recupera / Accetta" : "Accept"}
        </button>
      )}
      {item.status !== "discarded" && (
        <button
          className="btn-ghost text-xs text-rose-600 dark:text-rose-400"
          disabled={busy}
          title="Discard (it will not come back on re-scan)"
          aria-label="Discard listing"
          onClick={onDiscard}>
          ✕
        </button>
      )}
    </li>
  );
}
