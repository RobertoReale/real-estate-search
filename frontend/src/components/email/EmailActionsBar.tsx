import type { ImportCheckProgress, ImportCheckSummary, Settings } from "../../types";
import { ProgressBar } from "../ProgressBar";

export type SortKey = "date" | "sqm_price" | "price";

interface Props {
  itemsCount: number;
  selectedCount: number;
  allSelected: boolean;
  onToggleSelectAll: () => void;
  onAcceptSelected: () => void;
  onDiscardSelected: () => void;
  onDiscardAllShown: () => void;
  onCheckAvailability: () => void;
  onSaveCookie: (cookie: string) => Promise<void>;
  cookieInput: string;
  onCookieInputChange: (val: string) => void;
  localSettings: Settings | null;
  busy: boolean;
  checking: boolean;
  checkProgress: ImportCheckProgress | null;
  checkSummary: ImportCheckSummary | null;
  goneCount: number;
  onDiscardGone: () => void;
  sort: SortKey;
  onSortChange: (sort: SortKey) => void;
}

export function EmailActionsBar({
  itemsCount,
  selectedCount,
  allSelected,
  onToggleSelectAll,
  onAcceptSelected,
  onDiscardSelected,
  onDiscardAllShown,
  onCheckAvailability,
  onSaveCookie,
  cookieInput,
  onCookieInputChange,
  localSettings,
  busy,
  checking,
  checkProgress,
  checkSummary,
  goneCount,
  onDiscardGone,
  sort,
  onSortChange,
}: Props) {
  if (itemsCount === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <label className="flex items-center gap-1.5 text-xs font-medium t-muted cursor-pointer hover:text-blue-500 transition">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={onToggleSelectAll}
            className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
          />
          Seleziona tutti ({selectedCount})
        </label>
        <button
          className="btn py-1 px-2.5 text-xs bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-600 dark:text-emerald-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onAcceptSelected}>
          ✓ Accetta selezionati
        </button>
        <button
          className="btn py-1 px-2.5 text-xs bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition disabled:opacity-40"
          disabled={busy || selectedCount === 0}
          onClick={onDiscardSelected}>
          ✕ Scarta selezionati
        </button>
        <button
          className="btn-ghost text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition py-1 px-2"
          disabled={busy || itemsCount === 0}
          title="Scarta tutti gli annunci attualmente visualizzati (i filtri sopra rimangono applicati)."
          onClick={onDiscardAllShown}>
          🗑 Scarta tutti ({itemsCount})
        </button>
        <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-xl p-1 bg-slate-50 dark:bg-slate-900/50 shadow-sm">
          <input
            type="password"
            className="input text-xs py-1 px-2 w-32 sm:w-40 bg-white dark:bg-slate-900"
            placeholder={
              localSettings?.datadome_cookie_set
                ? "Cookie DataDome salvato"
                : "Incolla cookie DataDome..."
            }
            value={cookieInput}
            onChange={(e) => onCookieInputChange(e.target.value)}
            title="Incolla qui il cookie 'datadome' dal tuo browser per superare i blocchi dei portali"
          />
          <button
            className="btn py-1 px-2.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition disabled:opacity-50 flex items-center gap-1"
            disabled={busy || checking || itemsCount === 0}
            title="Verifica le pagine su portale per vedere quali sono ancora online e aggiornarne foto e dati. Se nessun annuncio è selezionato, controlla quelli non ancora verificati."
            onClick={async () => {
              if (cookieInput.trim() && cookieInput !== "***") {
                await onSaveCookie(cookieInput);
              }
              onCheckAvailability();
            }}>
            🔎 {selectedCount > 0 ? `Verifica selezionati (${selectedCount})` : "Verifica disponibilità online"}
          </button>
        </div>
        {goneCount > 0 && (
          <button
            className="btn py-1 px-2.5 text-xs bg-rose-600 hover:bg-rose-500 text-white font-semibold rounded-lg transition animate-pulse"
            disabled={busy || checking}
            title="Scarta in un colpo solo tutti gli annunci che il portale ha confermato come rimossi/innesistenti"
            onClick={onDiscardGone}>
            🚫 Scarta i {goneCount} rimossi
          </button>
        )}
        <label className="flex items-center gap-1.5 text-xs font-medium t-muted ml-auto">
          Ordina per:
          <select
            className="input text-xs py-1 px-2 rounded-lg"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as SortKey)}>
            <option value="date">Email più recente</option>
            <option value="sqm_price">€/m² (più economico)</option>
            <option value="price">Prezzo (più basso)</option>
          </select>
        </label>
      </div>

      {checking && (
        <ProgressBar
          done={checkProgress?.done ?? 0}
          total={checkProgress?.total ?? 0}
          indeterminate={!checkProgress || checkProgress.total <= 0}>
          {checkProgress
            ? `Verifica annuncio ${checkProgress.done} di ${checkProgress.total} — ${checkProgress.gone} già rimossi...`
            : "Avvio verifica..."}{" "}
          <span className="opacity-75 font-normal">
            (Una pagina ogni 6 secondi per evitare il blocco IP da parte dei portali)
          </span>
        </ProgressBar>
      )}

      {checkSummary && !checking && (
        <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
          <p className="font-medium">
            🔎 Esito verifica per {checkSummary.checked} annunci:{" "}
            <strong className="text-rose-600 dark:text-rose-400">
              {checkSummary.gone} non più online (rimossi)
            </strong>
            ,{" "}
            <strong className="text-emerald-600 dark:text-emerald-400">
              {checkSummary.online} ancora online e aggiornati
            </strong>
            {checkSummary.unknown > 0 && (
              <span className="t-dim">
                {" "}
                ({checkSummary.unknown} con esito incerto per blocco o errore di rete)
              </span>
            )}
            .
          </p>
          {checkSummary.cookie_refreshed ? (
            <p className="text-blue-600 dark:text-blue-400 font-medium">
              🔄 Cookie DataDome aggiornato in automatico{" "}
              {checkSummary.cookie_refreshed === 1
                ? "1 volta"
                : `${checkSummary.cookie_refreshed} volte`}{" "}
              durante la verifica per superare i controlli anti-robot.
            </p>
          ) : null}
          {checkSummary.last_error && (
            <p className="text-rose-600 dark:text-rose-400 font-medium">
              ❌ Dettaglio ultimo errore: {checkSummary.last_error}
            </p>
          )}
          {checkSummary.aborted && (
            <p className="text-amber-600 dark:text-amber-400 font-semibold">
              ⚠️ Il portale ha iniziato a bloccare le richieste, quindi la verifica è stata interrotta per proteggere l'IP di rete. Inserisci un nuovo cookie DataDome oppure riprova più tardi.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
