import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatPrice } from "../services/api";
import { PortalBadge } from "./PortalBadge";
import type {
  EmailScanParams, EmailScanProgress, EmailScanSummary, ImportCheckProgress,
  ImportCheckSummary, ImportedListing, ImportFilters, SearchProfile, Settings,
} from "../types";

/** The backend probes one ad at a time, spaced by `request_delay_seconds`;
 *  it caps a single request at this many. Kept in step with
 *  `email_import.MAX_CHECKS_PER_CALL`. */
const MAX_CHECKS = 50;

/** Sort orders for the review list. €/m² is the one that actually ranks value:
 *  a price alone says nothing without the surface it buys. */
type SortKey = "date" | "sqm_price" | "price";

/** The only derived figure the email itself allows: no listing page is ever
 *  fetched here, so price and surface are all there is to compare. */
function pricePerSqm(item: ImportedListing): number | null {
  if (!item.price || !item.sqm) return null;
  return Math.round(item.price / item.sqm);
}

function formatSqmPrice(item: ImportedListing): string {
  const value = pricePerSqm(item);
  if (value === null) return "";
  return item.contract === "rent"
    ? `${value.toLocaleString("it-IT")} €/m² per month`
    : `${value.toLocaleString("it-IT")} €/m²`;
}

function progressLabel(p: EmailScanProgress): string {
  if (p.phase === "connecting") return "Connecting to your mailbox…";
  if (p.phase === "searching") return "Searching the inbox…";
  if (p.phase === "fetching" && p.emails_total > 0) {
    return `Reading email ${p.emails_done} of ${p.emails_total}`
      + ` — ${p.staged} new listing${p.staged === 1 ? "" : "s"} staged`;
  }
  return "Starting…";
}

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void; // accepted imports become Properties: refresh the grid
}

const DEFAULT_SCAN: EmailScanParams = {
  mode: "portals", senders: "", since_days: 365, max_emails: 200,
};

const DEFAULT_FILTERS: ImportFilters = {
  profile_id: "", contract: "", city: "", min_price: "", max_price: "",
  rooms: "", q: "",
};

/** Review panel for listings mined from the user's inbox: nothing enters the
 *  dashboard without an explicit accept, and discards are remembered so a
 *  re-scan never resurrects them. */
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

  // The scan is one long POST, so its progress can only be observed from the
  // side: poll while it runs, and let the POST's own resolution end the loop.
  useEffect(() => {
    if (!scanning) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const p = await api.emailImportProgress();
        if (!cancelled) setProgress(p);
      } catch {
        // a dropped poll says nothing about the scan itself: keep waiting
      }
    };
    tick();
    const timer = setInterval(tick, 800);
    return () => { cancelled = true; clearInterval(timer); };
  }, [scanning]);

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

  // Same shape as the scan's poll, same reason: the check is one long POST.
  useEffect(() => {
    if (!checking) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const p = await api.importCheckProgress();
        if (!cancelled) setCheckProgress(p);
      } catch { /* a dropped poll says nothing about the check itself */ }
    };
    tick();
    const timer = setInterval(tick, 800);
    return () => { cancelled = true; clearInterval(timer); };
  }, [checking]);

  /** Asks the portals whether the selected listings still exist. */
  async function checkAvailability(ids: number[]) {
    // Skip already checked items if checking multiple listings to avoid redundant requests.
    // If only one item is selected, let the user force-check it even if already checked.
    const toCheck = ids.length === 1
      ? ids
      : ids.filter(id => {
          const item = items.find(i => i.id === id);
          return item && item.is_available === null;
        });

    if (toCheck.length === 0) {
      // silence here reads as a broken button: say why nothing was sent
      setError(ids.length > 0
        ? "All selected listings were already checked — select a single one to force a re-check."
        : "");
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

  const setFilter = (patch: Partial<ImportFilters>) =>
    setFilters((f) => ({ ...f, ...patch }));

  // Listings whose email never carried a price (or a surface) cannot be ranked
  // by it; they sink to the bottom rather than pretending to be the cheapest.
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
            Mine your own inbox for listing emails and review them here: accept
            what interests you, discard the rest. Your mailbox is accessed
            strictly read-only, and duplicates of listings already tracked are
            skipped automatically. Alert emails can be months old, so an ad may
            already be sold or withdrawn — "Open ↗" is the only way to find out,
            since this panel never visits the portals.
          </p>
          <p className="text-xs t-muted">
            Only ads <strong>hosted on Immobiliare.it or Idealista.it</strong>{" "}
            can be imported: the whole app is built around their listing IDs. An
            agency's own email counts only if it links to a portal ad — one that
            links to the agency's website instead brings back nothing, whatever
            sender you search for.
          </p>

          {!imapReady && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              ⚠️ IMAP is not configured yet — open ⚙️ Settings → "Email inbox
              import" and add host, username and app password first.
            </p>
          )}

          {/* scan controls: grid on a phone, flowing row from `sm` up. The
              `col-span-2` classes go inert once the container becomes a flex. */}
          <div className="grid grid-cols-2 gap-3 items-end p-3 rounded-xl panel
            sm:flex sm:flex-wrap">
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-xs t-muted">Look for</label>
              <select className="input w-full sm:w-56" value={scanParams.mode}
                onChange={(e) => setScanParams((p) => ({
                  ...p, mode: e.target.value as EmailScanParams["mode"],
                }))}>
                <option value="portals">Portal alert emails</option>
                <option value="address">Specific sender(s)</option>
                <option value="any">Any email linking a portal ad</option>
              </select>
            </div>
            {scanParams.mode === "address" && (
              <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[16rem]">
                <label className="text-xs t-muted"
                  title="Their emails must link an Immobiliare.it or Idealista.it ad: a link to the agency's own site cannot be imported">
                  Senders (comma-separated addresses or domains)
                </label>
                <input className="input w-full"
                  placeholder="e.g. agenzia@example.com, immobiliare.it"
                  value={scanParams.senders}
                  onChange={(e) => setScanParams((p) => ({
                    ...p, senders: e.target.value,
                  }))} />
              </div>
            )}
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Period</label>
              <select className="input w-full sm:w-36" value={scanParams.since_days}
                onChange={(e) => setScanParams((p) => ({
                  ...p, since_days: Number(e.target.value),
                }))}>
                <option value={30}>Last month</option>
                <option value={180}>Last 6 months</option>
                <option value={365}>Last year</option>
                <option value={1825}>Last 5 years</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted"
                title="Newest messages first; re-run the scan to go deeper (already imported listings are skipped)">
                Max emails
              </label>
              <select className="input w-full sm:w-28" value={scanParams.max_emails}
                onChange={(e) => setScanParams((p) => ({
                  ...p, max_emails: Number(e.target.value),
                }))}>
                {[50, 200, 500, 1000].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <button className="btn-primary col-span-2 sm:w-auto" onClick={scan}
              disabled={scanning || !imapReady
                || (scanParams.mode === "address" && !scanParams.senders.trim())}>
              {scanning ? "Scanning inbox…" : "Scan inbox"}
            </button>
          </div>

          {scanning && (
            <div className="space-y-1.5" role="status" aria-live="polite">
              <div className="h-1.5 w-full rounded-full overflow-hidden
                bg-slate-200 dark:bg-slate-700">
                {progress && progress.emails_total > 0 ? (
                  <div className="h-full bg-blue-500 transition-[width] duration-300"
                    style={{
                      width: `${Math.round(
                        (progress.emails_done / progress.emails_total) * 100,
                      )}%`,
                    }} />
                ) : (
                  // total unknown until the IMAP search answers: an
                  // indeterminate bar beats a 0% one that looks stuck
                  <div className="h-full w-1/3 bg-blue-500 animate-pulse" />
                )}
              </div>
              <p className="text-xs t-muted">
                {progress ? progressLabel(progress) : "Starting…"}
                {" "}Large mailboxes take a few minutes; you can keep using the
                dashboard meanwhile.
              </p>
            </div>
          )}

          {summary && !scanning && (
            <p className="text-xs t-muted">
              ✅ Scanned {summary.emails_scanned} emails
              ({summary.emails_with_listings} with listings) —{" "}
              <strong>{summary.imported} new listings staged</strong>,{" "}
              {summary.already_tracked} already tracked by your searches,{" "}
              {summary.already_imported} seen in a previous scan.
              {summary.blank_links > 0 && (
                <> {summary.blank_links} link
                  {summary.blank_links === 1 ? " was" : "s were"} skipped: the
                  email gave no price, size or name to review them by.</>
              )}
              {summary.blank_removed > 0 && (
                <> {summary.blank_removed} such row
                  {summary.blank_removed === 1 ? "" : "s"} left by earlier scans
                  {summary.blank_removed === 1 ? " was" : " were"} cleaned up.</>
              )}
            </p>
          )}

          {/* review filters */}
          <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-xs t-muted"
                title="Reuse the contract, city and excluded keywords of a search you already monitor">
                Filter like search
              </label>
              <select className="input w-full sm:w-52" value={filters.profile_id}
                onChange={(e) => setFilter({ profile_id: e.target.value })}>
                <option value="">— ad-hoc filters —</option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            {!filters.profile_id && (
              <>
                <div className="flex flex-col gap-1">
                  <label className="text-xs t-muted">Contract</label>
                  <select className="input w-full sm:w-28" value={filters.contract}
                    onChange={(e) => setFilter({
                      contract: e.target.value as ImportFilters["contract"],
                    })}>
                    <option value="">Any</option>
                    <option value="sale">🏠 Buy</option>
                    <option value="rent">🔑 Rent</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs t-muted">City</label>
                  <input className="input w-full sm:w-32" placeholder="e.g. Milano"
                    value={filters.city}
                    onChange={(e) => setFilter({ city: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs t-muted">Min €</label>
                  <input className="input w-full sm:w-24" type="number" value={filters.min_price}
                    onChange={(e) => setFilter({ min_price: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs t-muted">Max €</label>
                  <input className="input w-full sm:w-24" type="number" value={filters.max_price}
                    onChange={(e) => setFilter({ max_price: e.target.value })} />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-xs t-muted">Rooms</label>
                  <select className="input w-full sm:w-20" value={filters.rooms}
                    onChange={(e) => setFilter({ rooms: e.target.value })}>
                    <option value="">Any</option>
                    {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div className="col-span-2 flex flex-col gap-1 flex-1 sm:min-w-[10rem]">
                  <label className="text-xs t-muted">Text search</label>
                  <input className="input w-full" placeholder="in title/subject"
                    value={filters.q}
                    onChange={(e) => setFilter({ q: e.target.value })} />
                </div>
              </>
            )}
          </div>

          {error && <p className="accent-bad text-xs">{error}</p>}

          {/* bulk actions */}
          {items.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
                <input type="checkbox" checked={allSelected}
                  onChange={() => setSelected(
                    allSelected ? new Set() : new Set(items.map((i) => i.id)),
                  )} />
                Select all ({selected.size})
              </label>
              <button className="btn-ghost text-xs" disabled={busy || selected.size === 0}
                onClick={() => act([...selected], "accept")}>
                ✓ Accept selected
              </button>
              <button className="btn-ghost text-xs" disabled={busy || selected.size === 0}
                onClick={() => act([...selected], "discard")}>
                ✕ Discard selected
              </button>
              <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-800 rounded-lg p-1 bg-slate-50 dark:bg-slate-900/50">
                <input
                  type="password"
                  className="input text-xs py-0.5 px-1.5 w-28 sm:w-36"
                  placeholder={localSettings?.datadome_cookie_set ? "DataDome cookie saved" : "Paste datadome cookie..."}
                  value={cookieInput}
                  onChange={(e) => setCookieInput(e.target.value)}
                  title="Paste 'datadome' cookie from your real browser here to bypass blocks"
                />
                <button className="btn-ghost text-xs py-0.5 px-1.5"
                  disabled={busy || checking || selected.size === 0}
                  title={`Open each ad page once to see if it is still online. `
                    + `Slow on purpose (a few seconds apart), and at most ${MAX_CHECKS} per click.`}
                  onClick={async () => {
                    if (cookieInput.trim() && cookieInput !== "***") {
                      try {
                        const updated = await api.updateSettings({ datadome_cookie: cookieInput });
                        setLocalSettings(updated);
                        setCookieInput("***");
                      } catch (e) {
                        setError("Failed to save cookie: " + (e instanceof Error ? e.message : String(e)));
                        return;
                      }
                    }
                    checkAvailability([...selected]);
                  }}>
                  🔎 Check if still online
                </button>
              </div>
              {goneIds.length > 0 && (
                <button className="btn-ghost text-xs text-rose-600 dark:text-rose-400"
                  disabled={busy || checking}
                  title="Discard every listing the portal confirmed as removed"
                  onClick={() => act(goneIds, "discard")}>
                  🚫 Discard the {goneIds.length} removed
                </button>
              )}
              <label className="flex items-center gap-1.5 text-xs t-muted ml-auto">
                Sort by
                <select className="input text-xs py-1" value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}>
                  <option value="date">Newest email</option>
                  <option value="sqm_price">€/m² (cheapest first)</option>
                  <option value="price">Price (lowest first)</option>
                </select>
              </label>
            </div>
          )}

          {checking && (
            <div className="space-y-1.5" role="status" aria-live="polite">
              <div className="h-1.5 w-full rounded-full overflow-hidden
                bg-slate-200 dark:bg-slate-700">
                <div className="h-full bg-blue-500 transition-[width] duration-300"
                  style={{
                    width: checkProgress && checkProgress.total > 0
                      ? `${Math.round((checkProgress.done / checkProgress.total) * 100)}%`
                      : "0%",
                  }} />
              </div>
              <p className="text-xs t-muted">
                {checkProgress
                  ? `Checking listing ${checkProgress.done} of ${checkProgress.total}`
                    + ` — ${checkProgress.gone} already removed`
                  : "Starting…"}
                {" "}One ad page every few seconds: visiting them in a burst is
                how a home IP gets blocked by the portals.
              </p>
            </div>
          )}

          {checkSummary && !checking && (
            <p className="text-xs t-muted">
              🔎 Checked {checkSummary.checked}:{" "}
              <strong>{checkSummary.gone} no longer online</strong>,{" "}
              {checkSummary.online} still there
              {checkSummary.unknown > 0 && (
                <>, {checkSummary.unknown} the portal would not answer for
                  (blocked or unreachable — they keep whatever was known)</>
              )}.
              {checkSummary.last_error && (
                <span className="text-rose-600 dark:text-rose-400 block mt-1">
                  ❌ Detail on last failure: {checkSummary.last_error}
                </span>
              )}
              {checkSummary.aborted && (
                <span className="text-amber-600 dark:text-amber-400">
                  {" "}⚠️ The portal started refusing, so the check stopped
                  early rather than insisting — that would only deepen the
                  block, and your scans need the same connection. Try again
                  later.
                </span>
              )}
            </p>
          )}

          {items.length === 0 && (
            <p className="text-sm t-muted">
              Nothing to review{summary ? "" : " — run a scan above"}.
            </p>
          )}

          <ul className="space-y-2">
            {sortedItems.map((item) => (
              <li key={item.id}
                className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel">
                <input type="checkbox" checked={selected.has(item.id)}
                  onChange={() => setSelected((s) => {
                    const next = new Set(s);
                    if (next.has(item.id)) next.delete(item.id);
                    else next.add(item.id);
                    return next;
                  })} />
                <PortalBadge portal={item.portal} />
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-sm truncate">
                    {item.title || item.email_subject || `Listing ${item.portal_id}`}
                  </p>
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
                    ].filter(Boolean).join(" · ")}
                  </p>
                  {/* the subject usually names the saved search the alert came
                      from ("New listings for Milano Navigli"), which is the
                      only hint of *where* the property is: the email carries
                      no address, and this panel never opens the ad page */}
                  {item.title && item.email_subject && (
                    <p className="text-xs t-dim truncate opacity-70"
                      title={`${item.email_subject} — from ${item.email_from}`}>
                      ✉️ {item.email_subject}
                    </p>
                  )}
                </div>
                {formatSqmPrice(item) && (
                  <span className="text-xs font-medium shrink-0 px-2 py-1 rounded-lg
                    bg-slate-500/10"
                    title="Price divided by surface — the only comparable figure the email provides">
                    {formatSqmPrice(item)}
                  </span>
                )}
                <a href={item.url} target="_blank" rel="noreferrer"
                  className="accent-link text-xs shrink-0"
                  title="The ad may no longer exist on the portal">
                  Open ↗
                </a>
                <button className="btn-ghost text-xs" disabled={busy}
                  title="Add to the dashboard (deduplicated against existing properties)"
                  onClick={() => act([item.id], "accept")}>
                  ✓ Accept
                </button>
                <button className="btn-ghost text-xs text-rose-600 dark:text-rose-400"
                  disabled={busy} title="Discard (it will not come back on re-scan)"
                  aria-label="Discard listing"
                  onClick={() => act([item.id], "discard")}>
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
