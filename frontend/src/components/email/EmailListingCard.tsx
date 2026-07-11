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
    <li className={`flex flex-wrap items-center gap-3 sm:gap-4 p-3 sm:p-4 rounded-xl panel transition-all duration-200 hover:border-blue-500/40 ${
      selected ? "ring-2 ring-blue-500 border-blue-500 bg-blue-500/5" : ""
    }`}>
      <input
        type="checkbox"
        checked={selected}
        onChange={onToggleSelect}
        className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer shrink-0"
      />

      {/* Thumbnail clickable image */}
      <a
        href={item.url}
        target="_blank"
        rel="noreferrer"
        title="Apri annuncio originale sul portale"
        className="w-24 h-18 sm:w-28 sm:h-20 rounded-xl overflow-hidden shrink-0 bg-slate-200 dark:bg-slate-800 relative group shadow-sm block border border-slate-300/30 dark:border-slate-700/30">
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={item.title || "Foto annuncio"}
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
            className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-2xl text-slate-400 dark:text-slate-600">
            🏠
          </div>
        )}
        <div className="absolute bottom-1 left-1">
          <PortalBadge portal={item.portal} variant="overlay" />
        </div>
      </a>

      {/* Main Details */}
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="font-semibold text-sm sm:text-base hover:text-blue-500 transition truncate"
            title={item.title || item.email_subject || `Annuncio #${item.portal_id}`}>
            {item.title || item.email_subject || `Annuncio #${item.portal_id}`}
          </a>

          {/* Status badges */}
          {item.status && item.status !== "pending" && (
            <span
              className={`text-[11px] font-bold px-2 py-0.5 rounded-md shrink-0 ${
                item.status === "accepted"
                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                  : "bg-rose-500/20 text-rose-600 dark:text-rose-400 border border-rose-500/30"
              }`}>
              {item.status === "accepted" ? "✅ Accettato" : "🗑️ Scartato"}
            </span>
          )}

          {/* Availability badge */}
          {item.is_available === true && (
            <span
              className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shrink-0 flex items-center gap-1"
              title="Il portale ha confermato che la pagina dell'annuncio è ancora online e raggiungibile">
              🟢 Online sul portale
            </span>
          )}
          {item.is_available === false && (
            <span
              className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/20 shrink-0 flex items-center gap-1"
              title="Il portale ha risposto 'pagina non trovata' (404/rimosso)">
              🔴 Rimosso / Non disponibile
            </span>
          )}
          {item.is_available === null && (
            <span
              className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-500/10 t-dim border border-slate-500/15 shrink-0 flex items-center gap-1"
              title="Disponibilità non ancora verificata su portale. Usa 'Verifica se online'">
              ⚪ Non verificato
            </span>
          )}
        </div>

        {/* Price, Sqm, Rooms */}
        <p className="text-xs sm:text-sm font-medium t-dim truncate">
          {[
            formatPrice(item.price, item.contract),
            item.sqm ? `${item.sqm} m²` : "",
            item.rooms ? `${item.rooms} locali` : "",
            item.contract === "rent" ? "affitto" : "vendita",
            item.city ? item.city : "",
            item.email_date
              ? `email del ${new Date(item.email_date).toLocaleDateString("it-IT")}`
              : "",
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>

        {/* Email Source Info */}
        {item.email_subject && (
          <p
            className="text-xs t-dim truncate opacity-75"
            title={`${item.email_subject} — da ${item.email_from}`}>
            ✉️ <span className="italic">{item.email_subject}</span> ({item.email_from})
          </p>
        )}
      </div>

      {/* Sqm Price Chip */}
      {sqmPriceStr && (
        <span
          className="text-xs font-semibold shrink-0 px-2.5 py-1.5 rounded-lg bg-slate-500/10 border border-slate-500/15"
          title="Prezzo al metro quadro calcolato dall'email">
          {sqmPriceStr}
        </span>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1.5 shrink-0">
        <a
          href={item.url}
          target="_blank"
          rel="noreferrer"
          className="btn-ghost text-xs py-1.5 px-2.5"
          title="Apri pagina originale sul portale">
          Apri ↗
        </a>
        {item.status !== "accepted" && (
          <button
            className="btn py-1.5 px-2.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition"
            disabled={busy}
            title="Aggiungi al cruscotto principale (deduplicato automaticamente)"
            onClick={onAccept}>
            ✓ {item.status === "discarded" ? "Recupera / Accetta" : "Accetta"}
          </button>
        )}
        {item.status !== "discarded" && (
          <button
            className="btn-ghost text-xs py-1.5 px-2.5 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition"
            disabled={busy}
            title="Scarta annuncio (non verrà ricaricato alle prossime scansioni)"
            aria-label="Scarta annuncio"
            onClick={onDiscard}>
            ✕ Scarta
          </button>
        )}
      </div>
    </li>
  );
}
