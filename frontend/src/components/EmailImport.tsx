import { useCallback, useEffect, useMemo, useState } from "react";
import { useProgressPoll } from "../hooks/useProgressPoll";
import { api } from "../services/api";
import type {
  EmailScanParams,
  EmailScanProgress,
  EmailScanSummary,
  ImportCheckProgress,
  ImportCheckSummary,
  ImportedListing,
  ImportFilters,
  SearchProfile,
  Settings,
} from "../types";
import { EmailActionsBar, type SortKey } from "./email/EmailActionsBar";
import { EmailListingCard, pricePerSqm } from "./email/EmailListingCard";
import { EmailReviewFilters } from "./email/EmailReviewFilters";
import { EmailScanForm } from "./email/EmailScanForm";

const MAX_CHECKS = 50;

const DEFAULT_SCAN: EmailScanParams = {
  mode: "portals",
  senders: "",
  since_days: 365,
  max_emails: 200,
};

const DEFAULT_FILTERS: ImportFilters = {
  status: "pending",
  profile_id: "",
  contract: "",
  city: "",
  min_price: "",
  max_price: "",
  rooms: "",
  q: "",
};

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void;
}

/** Review panel for listings mined from the user's inbox. */
export default function EmailImport({ profiles, settings, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [scanParams, setScanParams] = useState<EmailScanParams>(DEFAULT_SCAN);
  const [scanning, setScanning] = useState(false);
  const [summary, setSummary] = useState<EmailScanSummary | null>(null);
  const [filters, setFilters] = useState<ImportFilters>(DEFAULT_FILTERS);
  const [items, setItems] = useState<ImportedListing[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<EmailScanProgress | null>(null);
  const [sort, setSort] = useState<SortKey>("date");
  const [checking, setChecking] = useState(false);
  const [checkProgress, setCheckProgress] = useState<ImportCheckProgress | null>(null);
  const [checkSummary, setCheckSummary] = useState<ImportCheckSummary | null>(null);
  const [localSettings, setLocalSettings] = useState<Settings | null>(null);
  const [cookieInput, setCookieInput] = useState("");

  useEffect(() => {
    setLocalSettings(settings);
    if (settings?.datadome_cookie_set) {
      setCookieInput("***");
    } else {
      setCookieInput("");
    }
  }, [settings]);

  const imapReady = Boolean(
    settings?.imap_host && settings.imap_user && settings.imap_password_set,
  );

  const load = useCallback(async () => {
    try {
      setItems(await api.getImportedListings(filters));
      setSelected(new Set());
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }, [filters]);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  useProgressPoll(scanning, api.emailImportProgress, setProgress, 800);
  useProgressPoll(checking, api.importCheckProgress, setCheckProgress, 800);

  async function scan() {
    setScanning(true);
    setError("");
    setSummary(null);
    setProgress(null);
    try {
      setSummary(await api.emailImportScan(scanParams));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setScanning(false);
      setProgress(null);
    }
  }

  async function checkAvailability(ids: number[]) {
    let toCheck: number[] = [];
    if (ids.length === 0) {
      toCheck = items.filter((i) => i.is_available === null).map((i) => i.id);
      if (toCheck.length === 0 && items.length > 0) {
        toCheck = items.map((i) => i.id);
      }
    } else if (ids.length === 1) {
      toCheck = ids;
    } else {
      toCheck = ids.filter((id) => {
        const item = items.find((i) => i.id === id);
        return item && item.is_available === null;
      });
      if (toCheck.length === 0) {
        toCheck = ids;
      }
    }

    if (toCheck.length === 0) {
      setError(
        "Nessun annuncio da verificare. Scansiona le email o seleziona un annuncio specifico per forzare il ricalcolo.",
      );
      return;
    }
    setChecking(true);
    setError("");
    setCheckSummary(null);
    setCheckProgress(null);
    try {
      setCheckSummary(await api.checkImported(toCheck.slice(0, MAX_CHECKS)));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setChecking(false);
      setCheckProgress(null);
    }
  }

  async function act(ids: number[], action: "accept" | "discard") {
    if (ids.length === 0) return;
    setBusy(true);
    setError("");
    try {
      if (ids.length === 1) {
        await (action === "accept"
          ? api.acceptImported(ids[0])
          : api.discardImported(ids[0]));
      } else {
        await api.bulkImported(ids, action);
      }
      await load();
      if (action === "accept") onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  const setFilterPatch = (patch: Partial<ImportFilters>) =>
    setFilters((f) => ({ ...f, ...patch }));

  async function discardAllShown() {
    if (items.length === 0) return;
    const ok = window.confirm(
      `Discard all ${items.length} listing${items.length === 1 ? "" : "s"} ` +
        "shown here? They won't come back on future scans.",
    );
    if (ok) await act(items.map((i) => i.id), "discard");
  }

  async function saveCookie(cookie: string) {
    try {
      const updated = await api.updateSettings({ datadome_cookie: cookie });
      setLocalSettings(updated);
      setCookieInput("***");
      setError("");
    } catch (e) {
      setError("Failed to save cookie: " + (e instanceof Error ? e.message : String(e)));
    }
  }

  const sortedItems = useMemo(() => {
    const rank = (item: ImportedListing) =>
      sort === "price" ? item.price : sort === "sqm_price" ? pricePerSqm(item) : null;
    if (sort === "date") return items;
    return [...items].sort((a, b) => {
      const [x, y] = [rank(a), rank(b)];
      if (x === null) return y === null ? 0 : 1;
      if (y === null) return -1;
      return x - y;
    });
  }, [items, sort]);

  const allSelected = items.length > 0 && selected.size === items.length;
  const goneIds = useMemo(
    () => items.filter((i) => i.is_available === false).map((i) => i.id),
    [items],
  );

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-base">
          📥 Import from email{" "}
          {items.length > 0 && open && (
            <span className="t-muted text-sm">({items.length} to review)</span>
          )}
        </h2>
        <button className="btn-ghost" onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Open"}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-4">
          <p className="text-xs t-muted">
            Mine your own inbox for listing emails and review them here: accept what
            interests you, discard the rest. Your mailbox is accessed strictly read-only,
            and duplicates of listings already tracked are skipped automatically. Alert
            emails can be months old, so an ad may already be sold or withdrawn — "Open
            ↗" is the only way to find out, since this panel never visits the portals.
          </p>
          <p className="text-xs t-muted">
            Only ads <strong>hosted on Immobiliare.it or Idealista.it</strong> can be
            imported: the whole app is built around their listing IDs. An agency's own
            email counts only if it links to a portal ad — one that links to the agency's
            website instead brings back nothing, whatever sender you search for.
          </p>

          {!imapReady && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              ⚠️ IMAP is not configured yet — open ⚙️ Settings → "Email inbox import" and
              add host, username and app password first.
            </p>
          )}

          <EmailScanForm
            scanParams={scanParams}
            onScanParamsChange={setScanParams}
            onScan={scan}
            scanning={scanning}
            progress={progress}
            imapReady={imapReady}
            summary={summary}
          />

          <EmailReviewFilters
            filters={filters}
            onFilterChange={setFilterPatch}
            profiles={profiles}
          />

          {error && <p className="accent-bad text-xs">{error}</p>}

          <EmailActionsBar
            itemsCount={items.length}
            selectedCount={selected.size}
            allSelected={allSelected}
            onToggleSelectAll={() =>
              setSelected(
                allSelected ? new Set() : new Set(items.map((i) => i.id)),
              )
            }
            onAcceptSelected={() => act([...selected], "accept")}
            onDiscardSelected={() => act([...selected], "discard")}
            onDiscardAllShown={discardAllShown}
            onCheckAvailability={() => checkAvailability([...selected])}
            onSaveCookie={saveCookie}
            cookieInput={cookieInput}
            onCookieInputChange={setCookieInput}
            localSettings={localSettings}
            busy={busy}
            checking={checking}
            checkProgress={checkProgress}
            checkSummary={checkSummary}
            goneCount={goneIds.length}
            onDiscardGone={() => act(goneIds, "discard")}
            sort={sort}
            onSortChange={setSort}
          />

          {items.length === 0 && (
            <p className="text-sm t-muted">
              Nothing to review{summary ? "" : " — run a scan above"}.
            </p>
          )}

          <ul className="space-y-2">
            {sortedItems.map((item) => (
              <EmailListingCard
                key={item.id}
                item={item}
                selected={selected.has(item.id)}
                onToggleSelect={() =>
                  setSelected((s) => {
                    const next = new Set(s);
                    if (next.has(item.id)) next.delete(item.id);
                    else next.add(item.id);
                    return next;
                  })
                }
                onAccept={() => act([item.id], "accept")}
                onDiscard={() => act([item.id], "discard")}
                busy={busy}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
