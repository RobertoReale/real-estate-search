import { useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../services/api";
import { PortalBadge } from "./PortalBadge";
import type {
  AssistantSearch, ProfileResults, SearchBuilderParams, SearchBuilderUrls,
  SearchProfile, Settings,
} from "../types";

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void;
}

const statusBadge: Record<string, { label: string; cls: string }> = {
  ok: { label: "OK", cls: "chip-emerald" },
  blocked: { label: "Blocked (will retry)", cls: "chip-amber" },
  error: { label: "Error", cls: "chip-rose" },
};

const EMPTY_BUILDER: SearchBuilderParams = {
  city: "", province: "", zone: "", contract: "sale",
  min_price: "", max_price: "", min_rooms: "", max_rooms: "", min_sqm: "",
};

const ASSISTANT_EXAMPLES = [
  "trilocale in affitto a Milano sotto i 1.200 € al mese",
  "bilocale a Milano zona Navigli o trilocale zona Lambrate, max 400k",
  "casa a Sesto San Giovanni (MI) almeno 90 mq, budget 280 mila",
];

/** The assistant answers with numbers; the builder form holds strings. */
function paramsFromAssistant(search: AssistantSearch): SearchBuilderParams {
  const str = (v: number | null) => (v === null ? "" : String(v));
  return {
    city: search.params.city,
    province: search.params.province,
    zone: search.params.zone,
    contract: search.params.contract,
    min_price: str(search.params.min_price),
    max_price: str(search.params.max_price),
    min_rooms: str(search.params.min_rooms),
    max_rooms: str(search.params.max_rooms),
    min_sqm: str(search.params.min_sqm),
  };
}

/** Convert extracted or stored profile criteria to form strings. */
function paramsFromProfile(params?: SearchProfile["params"]): SearchBuilderParams {
  if (!params) return EMPTY_BUILDER;
  const str = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  return {
    city: params.city || "",
    province: params.province || "",
    zone: params.zone || "",
    contract: params.contract || "sale",
    min_price: str(params.min_price),
    max_price: str(params.max_price),
    min_rooms: str(params.min_rooms),
    max_rooms: str(params.max_rooms),
    min_sqm: str(params.min_sqm),
  };
}

/** Auto-label for a profile created from a parsed search. */
function searchLabel(search: AssistantSearch): string {
  const p = search.params;
  return [
    p.contract === "rent" ? "Rent" : "Buy",
    p.city,
    p.zone,
    p.min_rooms ? `${p.min_rooms}+ rooms` : "",
  ].filter(Boolean).join(" · ");
}

/** Surfaces the globally excluded keywords (set once in Settings, applied to
 *  every search) next to the per-search field, so what gets discarded is
 *  visible where the user is looking instead of a separate modal. */
function GlobalKeywordsHint({ settings }: { settings: Settings | null }) {
  const words = settings?.excluded_keywords ?? [];
  if (!words.length) return null;
  return (
    <p className="text-xs t-dim -mt-1.5">
      🌐 Always excluded for every search (from Settings): {words.join(", ")}
    </p>
  );
}

/** The full set of keywords that discard a listing for this profile: global
 *  (Settings) plus this search's own extras, deduplicated case-insensitively
 *  so the same word set from both places doesn't read as doubled. */
function combinedKeywords(profile: SearchProfile, settings: Settings | null): string[] {
  const own = profile.excluded_keywords.split(",").map((k) => k.trim()).filter(Boolean);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const kw of [...(settings?.excluded_keywords ?? []), ...own]) {
    const key = kw.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(kw);
  }
  return result;
}

/** A channel is "ready" only when it is enabled AND has the credentials it
 *  needs — mirroring the backend's own gating in notifier.py, so the UI
 *  never claims a delivery route that would silently drop messages. */
function channelReadiness(settings: Settings | null) {
  return {
    telegram: Boolean(
      settings?.telegram_enabled &&
      settings.telegram_token_set &&
      settings.telegram_chat_id,
    ),
    email: Boolean(
      settings?.email_enabled && settings.smtp_host && settings.email_to,
    ),
  };
}

export default function SearchProfiles({ profiles, settings, onChanged }: Props) {
  const [mode, setMode] = useState<
    "closed" | "url" | "builder" | "assistant" | "multi"
  >("closed");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [keywords, setKeywords] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  // set while editing an existing profile via the "url" form, so submitUrl
  // knows whether to PUT over it instead of POSTing a new one
  const [editingId, setEditingId] = useState<number | null>(null);

  // builder state
  const [params, setParams] = useState<SearchBuilderParams>(EMPTY_BUILDER);
  const [built, setBuilt] = useState<SearchBuilderUrls | null>(null);
  const [usePortals, setUsePortals] = useState({ immobiliare: true, idealista: true });

  // assistant state: the parsed read-back stays visible in the builder, so
  // the user can see what the sentence was understood to mean
  const [query, setQuery] = useState("");
  const [asking, setAsking] = useState(false);
  const [assistant, setAssistant] = useState<AssistantSearch | null>(null);
  // a query with "o"/"oppure" yields several alternatives, reviewed as a list
  const [multi, setMulti] = useState<AssistantSearch[]>([]);

  // delete dialog: the searches awaiting confirmation (one row, or a whole
  // selection), plus what their results would cost — fetched on open, for the
  // set as a whole, since "kept: another search covers it" only counts searches
  // that survive the delete
  const [deleting, setDeleting] = useState<SearchProfile[] | null>(null);
  const [results, setResults] = useState<ProfileResults | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  // bulk selection: acting on every search one row at a time is the tedium this
  // exists to remove (pausing them all before a holiday, muting a noisy set…)
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);

  const ready = channelReadiness(settings);
  const channelOptions = [
    {
      value: "",
      label: "🔔 All channels",
      ok: ready.telegram || ready.email,
      warn: "No notification channel is set up yet — this search won't send alerts. Configure Telegram or Email in ⚙️ Settings.",
    },
    {
      value: "telegram",
      label: ready.telegram ? "📨 Telegram only" : "📨 Telegram only (not set up)",
      ok: ready.telegram,
      warn: "Telegram is not set up — this search won't send alerts. Add the bot token and chat ID in ⚙️ Settings.",
    },
    {
      value: "email",
      label: ready.email ? "✉️ Email only" : "✉️ Email only (not set up)",
      ok: ready.email,
      warn: "Email is not set up — this search won't send alerts. Configure SMTP in ⚙️ Settings.",
    },
    {
      // silence is a choice, not a misconfiguration: keep the search running
      // and its cards flowing into the dashboard, just never get pinged for it
      value: "none",
      label: "🔕 No notifications",
      ok: true,
      warn: "",
    },
  ];

  const selectedProfiles = profiles.filter((p) => selected.has(p.id));
  const allSelected = profiles.length > 0 && selected.size === profiles.length;

  function toggleOne(id: number) {
    setSelected((s) => {
      const next = new Set(s);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  }

  /** Runs a bulk action, then clears the selection: the rows it acted on may no
   *  longer exist (delete), and a stale checkbox is worse than none. */
  async function runBulk(
    ids: number[],
    action: "activate" | "pause" | "notify",
    notifyChannels?: string,
  ) {
    setBulkBusy(true);
    setError("");
    try {
      await api.bulkProfiles(ids, action, { notifyChannels });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBulkBusy(false);
    }
  }

  const setParam = (patch: Partial<SearchBuilderParams>) => {
    setParams((p) => ({ ...p, ...patch }));
    setBuilt(null); // generated URLs are stale as soon as an input changes
    // a warning like "I could not tell which city" is answered by the very
    // edit the user is making: keeping it on screen would be nagging
    setAssistant((a) => (a && a.warnings.length ? { ...a, warnings: [] } : a));
  };

  /** Opens the delete dialog and asks the backend what these searches' results
   *  amount to. The counts arrive after the dialog does (`results === null` is
   *  the loading state): the question is worth asking even while they load. */
  async function askDelete(targets: SearchProfile[]) {
    setDeleting(targets);
    setResults(null);
    setDeleteError("");
    try {
      setResults(await api.getProfilesResults(targets.map((p) => p.id)));
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e));
    }
  }

  async function confirmDelete(deleteResults: boolean) {
    if (!deleting) return;
    setDeleteBusy(true);
    setDeleteError("");
    try {
      await api.bulkProfiles(deleting.map((p) => p.id), "delete", { deleteResults });
      setDeleting(null);
      setSelected(new Set());
      onChanged();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeleteBusy(false);
    }
  }

  function resetForm() {
    setName(""); setUrl(""); setKeywords(""); setError("");
    setParams(EMPTY_BUILDER); setBuilt(null);
    setQuery(""); setAssistant(null); setMulti([]);
    setEditingId(null);
    setMode("closed");
  }

  function editProfile(p: SearchProfile) {
    setName(p.name);
    setUrl(p.search_url);
    setKeywords(p.excluded_keywords);
    setEditingId(p.id);
    setError("");
    if (p.params && (p.params.city || p.params.min_price || p.params.min_rooms || p.params.zone)) {
      const formParams = paramsFromProfile(p.params);
      setParams(formParams);
      setBuilt({
        immobiliare: p.portal === "immobiliare" ? p.search_url : "",
        idealista: p.portal === "idealista" ? p.search_url : "",
      });
      setUsePortals({
        immobiliare: p.portal === "immobiliare",
        idealista: p.portal === "idealista",
      });
      setMode("builder");
      // the profile only carries its own portal's URL; fill in the other
      // portal's slot too, so ticking its checkbox has a URL to save instead
      // of silently no-opping (createFromBuilder skips an empty built[portal])
      api.buildSearchUrls(formParams).then((urls) => {
        setBuilt((b) => b && {
          immobiliare: b.immobiliare || urls.immobiliare,
          idealista: b.idealista || urls.idealista,
        });
      }).catch(() => {});
    } else {
      setMode("url");
    }
  }

  function editInBuilder(search: AssistantSearch) {
    setAssistant(search);
    setParams(paramsFromAssistant(search));
    // the assistant only returns URLs when it recognised a city; otherwise
    // the builder opens pre-filled and waits for the missing piece
    setBuilt(search.urls);
    setMode("builder");
  }

  async function extractParamsFromUrl() {
    if (!url.trim()) return;
    setError("");
    try {
      const extracted = await api.parseSearchUrl(url);
      setParams(paramsFromProfile(extracted));
      setBuilt({
        immobiliare: url.includes("immobiliare.it") ? url : "",
        idealista: url.includes("idealista.it") ? url : "",
      });
      setUsePortals({
        immobiliare: url.includes("immobiliare.it"),
        idealista: url.includes("idealista.it"),
      });
      setMode("builder");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function ask() {
    if (!query.trim()) return;
    setAsking(true);
    setError("");
    try {
      const result = await api.askAssistant(query);
      if (result.searches.length > 1) {
        setMulti(result.searches);
        setMode("multi");
      } else {
        editInBuilder(result.searches[0]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setAsking(false);
    }
  }

  function normalizeSearchUrl(targetUrl: string): string {
    if (!targetUrl) return "";
    try {
      const u = new URL(targetUrl.trim());
      u.searchParams.delete("id");
      u.searchParams.delete("imm_source");
      u.searchParams.delete("pag");
      const pathname = u.pathname.replace(/\/+$/, "");
      const params = Array.from(u.searchParams.entries()).sort((a, b) => a[0].localeCompare(b[0]));
      const search = params.length > 0 ? "?" + new URLSearchParams(params).toString() : "";
      return `${u.origin}${pathname}${search}`.toLowerCase();
    } catch {
      return targetUrl.trim().replace(/\/+$/, "").toLowerCase();
    }
  }

  function normalizeSearchKeywords(kw: string): string {
    return (kw || "").split(",")
      .map(k => k.trim().toLowerCase())
      .filter(Boolean)
      .sort()
      .join(",");
  }

  function findDuplicateProfile(targetUrl: string, targetKw: string, excludeId?: number): SearchProfile | undefined {
    const normUrl = normalizeSearchUrl(targetUrl);
    const normKw = normalizeSearchKeywords(targetKw);
    return profiles.find(p => {
      if (excludeId !== undefined && p.id === excludeId) return false;
      return normalizeSearchUrl(p.search_url) === normUrl && normalizeSearchKeywords(p.excluded_keywords) === normKw;
    });
  }

  async function createFromMulti() {
    setSaving(true);
    setError("");
    let addedCount = 0;
    try {
      for (const search of multi) {
        if (!search.urls) continue; // no city recognised: cannot build URLs
        for (const portal of ["immobiliare", "idealista"] as const) {
          if (!usePortals[portal]) continue;
          if (findDuplicateProfile(search.urls[portal], keywords)) continue;
          await api.createProfile({
            name: `${searchLabel(search)} (${portal})`,
            search_url: search.urls[portal],
            excluded_keywords: keywords,
            is_active: true,
          });
          addedCount++;
        }
      }
      if (addedCount === 0 && multi.some(s => s.urls)) {
        setError("Tutte le ricerche selezionate sono già presenti e monitorate.");
      } else {
        resetForm();
        onChanged();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  async function submitUrl() {
    setSaving(true);
    setError("");
    try {
      const dup = findDuplicateProfile(url, keywords, editingId !== null ? editingId : undefined);
      if (dup) {
        setError(`Esiste già una ricerca monitorata identica ('${dup.name}') con lo stesso URL e parole chiave escluse.`);
        setSaving(false);
        return;
      }
      if (editingId !== null) {
        const current = profiles.find((p) => p.id === editingId);
        await api.updateProfile(editingId, {
          name: name || "Untitled search",
          search_url: url,
          excluded_keywords: keywords,
          notify_channels: current?.notify_channels ?? "",
          is_active: current?.is_active ?? true,
        });
      } else {
        await api.createProfile({
          name: name || "Untitled search",
          search_url: url,
          excluded_keywords: keywords,
          is_active: true,
        });
      }
      resetForm();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  async function generate() {
    setError("");
    try {
      setBuilt(await api.buildSearchUrls(params));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  async function createFromBuilder() {
    if (!built) return;
    setSaving(true);
    setError("");
    const label = name || [
      params.contract === "rent" ? "Rent" : "Buy", params.city, params.zone,
    ].filter(Boolean).join(" · ");
    try {
      if (editingId !== null) {
        const current = profiles.find((p) => p.id === editingId);
        if (current) {
          const targetPortal = (current.portal === "immobiliare" || current.portal === "idealista")
            ? (current.portal as "immobiliare" | "idealista")
            : (usePortals.immobiliare ? "immobiliare" : "idealista");
          const targetUrl = built[targetPortal] || current.search_url;
          const dup = findDuplicateProfile(targetUrl, keywords, editingId);
          if (dup) {
            setError(`Esiste già una ricerca monitorata identica ('${dup.name}') con lo stesso URL e parole chiave escluse.`);
            setSaving(false);
            return;
          }
          await api.updateProfile(editingId, {
            name: name || current.name,
            search_url: targetUrl,
            excluded_keywords: keywords,
            notify_channels: current.notify_channels ?? "",
            is_active: current.is_active ?? true,
          });
          for (const portal of ["immobiliare", "idealista"] as const) {
            if (usePortals[portal] && portal !== targetPortal && built[portal]) {
              if (!findDuplicateProfile(built[portal], keywords, editingId)) {
                await api.createProfile({
                  name: `${name || label} (${portal})`,
                  search_url: built[portal],
                  excluded_keywords: keywords,
                  is_active: true,
                });
              }
            }
          }
        }
      } else {
        let addedCount = 0;
        for (const portal of ["immobiliare", "idealista"] as const) {
          if (!usePortals[portal]) continue;
          if (findDuplicateProfile(built[portal], keywords)) continue;
          await api.createProfile({
            name: `${label} (${portal})`,
            search_url: built[portal],
            excluded_keywords: keywords,
            is_active: true,
          });
          addedCount++;
        }
        if (addedCount === 0) {
          setError("Esiste già una ricerca monitorata identica per i parametri selezionati.");
          setSaving(false);
          return;
        }
      }
      resetForm();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }


  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold text-base">
          🔍 Monitored searches{" "}
          <span className="t-muted text-sm">({profiles.length})</span>
        </h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "assistant") setMode("assistant"); }}>
            {mode === "assistant" ? "Cancel" : "💬 Just describe it"}
          </button>
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "builder") setMode("builder"); }}>
            {mode === "builder" ? "Cancel" : "🧭 Build a search"}
          </button>
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "url") setMode("url"); }}>
            {mode === "url" ? "Cancel" : "🔗 Paste a URL"}
          </button>
        </div>
      </div>

      {mode === "assistant" && (
        <div className="mb-4 p-4 rounded-xl panel space-y-3">
          <p className="text-xs t-muted">
            Describe what you are looking for in plain Italian or English —
            even several alternatives at once ("bilocale in zona X o trilocale
            in zona Y"). The text is parsed on your PC — nothing is sent to
            any AI service — and you review every search before it is saved.
          </p>
          <div className="flex flex-wrap gap-2">
            <input
              className="input flex-1 basis-full sm:basis-auto sm:min-w-[18rem]"
              placeholder="e.g. trilocale in affitto a Milano sotto i 1.200 € al mese"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              autoFocus />
            <button className="btn-primary" onClick={ask}
              disabled={asking || !query.trim()}>
              {asking ? "Reading…" : "Understand it →"}
            </button>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs t-dim">Try:</span>
            {ASSISTANT_EXAMPLES.map((example) => (
              <button key={example}
                className="text-xs chip-blue px-2 py-1 rounded-lg hover:opacity-80 transition"
                onClick={() => setQuery(example)}>
                {example}
              </button>
            ))}
          </div>
          {error && <p className="accent-bad text-xs">{error}</p>}
        </div>
      )}

      {mode === "multi" && (
        <div className="mb-4 p-4 rounded-xl panel space-y-3">
          <div className="flex items-center gap-2">
            <p className="text-xs t-muted flex-1">
              I read <strong>{multi.length} alternative searches</strong> in
              your sentence. Check each one (open the links to verify the
              results), then create all the profiles at once.
            </p>
            <button className="text-xs accent-link"
              onClick={() => setMode("assistant")}>
              ✏️ Reword
            </button>
          </div>
          {multi.map((search, idx) => (
            <div key={idx} className="p-3 rounded-xl panel space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded chip-blue">
                  Search {idx + 1}
                </span>
                {search.interpretation.map((part) => (
                  <span key={part}
                    className="text-xs chip-emerald px-2 py-1 rounded-lg font-medium">
                    {part}
                  </span>
                ))}
                <button className="text-xs accent-link ml-auto"
                  title="Adjust this search in the builder form"
                  onClick={() => editInBuilder(search)}>
                  Edit
                </button>
                <button className="t-dim hover:text-rose-500 transition text-xs btn-focus"
                  title="Drop this alternative" aria-label="Drop this alternative"
                  onClick={() => setMulti((m) => m.filter((_, i) => i !== idx))}>
                  ✕
                </button>
              </div>
              {search.notes.map((note) => (
                <p key={note} className="text-xs t-muted">ℹ️ {note}</p>
              ))}
              {search.warnings.map((warning) => (
                <p key={warning}
                  className="text-xs text-amber-600 dark:text-amber-400">
                  ⚠️ {warning}
                </p>
              ))}
              {(["immobiliare", "idealista"] as const).map((portal) => {
                const urls = search.urls;
                if (!urls || !usePortals[portal]) return null;
                return (
                  <div key={portal} className="flex items-center gap-2 text-xs">
                    <PortalBadge portal={portal} />
                    <span className="t-muted truncate flex-1">{urls[portal]}</span>
                    <a href={urls[portal]} target="_blank" rel="noreferrer"
                      className="accent-link shrink-0">
                      Open ↗
                    </a>
                  </div>
                );
              })}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-3">
            {(["immobiliare", "idealista"] as const).map((portal) => (
              <label key={portal}
                className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
                <input type="checkbox" checked={usePortals[portal]}
                  onChange={(e) =>
                    setUsePortals((u) => ({ ...u, [portal]: e.target.checked }))} />
                {portal}
              </label>
            ))}
            <input className="input flex-1 basis-full sm:basis-auto sm:min-w-[14rem]"
              placeholder="Extra excluded keywords (optional, comma-separated)"
              value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </div>
          <GlobalKeywordsHint settings={settings} />
          {error && <p className="accent-bad text-xs">{error}</p>}
          <button className="btn-primary" onClick={createFromMulti}
            disabled={
              saving
              || multi.every((s) => !s.urls)
              || (!usePortals.immobiliare && !usePortals.idealista)
            }>
            {saving ? "Saving…" : `Create ${
              multi.filter((s) => s.urls).length
              * (Number(usePortals.immobiliare) + Number(usePortals.idealista))
            } profiles`}
          </button>
        </div>
      )}

      {mode === "url" && (
        <div className="mb-4 p-4 rounded-xl panel space-y-3">
          <p className="text-xs t-muted">
            Go to Immobiliare.it or Idealista, set zone and filters on the map,
            then copy the results page URL here.
          </p>
          {/* The one thing a new user must understand: pasting a URL is not a
              fallback, it is the most powerful way to search — every portal
              filter is honored, including the ones the builder cannot express. */}
          <p className="text-xs rounded-lg px-3 py-2 chip-blue">
            💡 This is how you use <strong>every</strong> portal filter — bathrooms,
            floor, elevator, terrace, energy class, property type, exclude auctions,
            and so on. Set them on the portal, then paste the URL: the app monitors
            exactly that search. The two helpers above ("Just describe it" / "Build
            a search") only cover city, price, rooms and surface.
          </p>
          <div className="grid sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder="Name (e.g. 3 rooms South Milan)"
              value={name} onChange={(e) => setName(e.target.value)} />
            <input className="input w-full" placeholder="Extra excluded keywords (optional, comma-separated)"
              value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </div>
          <GlobalKeywordsHint settings={settings} />
          <div className="flex flex-wrap sm:flex-nowrap gap-2">
            <input className="input w-full"
              placeholder="https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…"
              value={url} onChange={(e) => setUrl(e.target.value)} />
            {url.trim() && (
              <button className="btn-secondary whitespace-nowrap text-xs px-3"
                type="button"
                title="Extract city and filters into the Builder form"
                onClick={extractParamsFromUrl}>
                🪄 Extract parameters
              </button>
            )}
          </div>
          {error && <p className="accent-bad text-xs">{error}</p>}
          <button className="btn-primary" onClick={submitUrl} disabled={saving || !url}>
            {saving ? "Saving…" : editingId !== null ? "Save changes" : "Save profile"}
          </button>
        </div>
      )}

      {mode === "builder" && (
        <div className="mb-4 p-4 rounded-xl panel space-y-3">
          {assistant ? (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs t-muted">I understood:</span>
                {assistant.interpretation.map((part) => (
                  <span key={part}
                    className="text-xs chip-emerald px-2 py-1 rounded-lg font-medium">
                    {part}
                  </span>
                ))}
                <button className="text-xs accent-link ml-auto"
                  onClick={() => setMode("assistant")}>
                  ✏️ Reword
                </button>
              </div>
              {/* assumptions the parser had to make: visible, not buried */}
              {assistant.notes.map((note) => (
                <p key={note} className="text-xs t-muted">ℹ️ {note}</p>
              ))}
              {assistant.warnings.map((warning) => (
                <p key={warning}
                  className="text-xs text-amber-600 dark:text-amber-400">
                  ⚠️ {warning}
                </p>
              ))}
              <p className="text-xs t-dim">
                Check the fields below — correct anything the parser got wrong.
              </p>
            </div>
          ) : (
            <p className="text-xs t-muted">
              Pick your criteria and the correct portal search URLs are generated
              for you — no copy/paste from the browser needed. This covers the
              basics (city, price, rooms, surface); for bathrooms, floor,
              features or energy class, set them on the portal and use{" "}
              <button className="accent-link underline"
                onClick={() => setMode("url")}>🔗 Paste a URL</button> instead.
            </p>
          )}
          {/* two columns on a phone, one flowing row from `sm` up — the
              `col-span-2` below is inert once the container turns into a flex */}
          <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Contract</label>
              <select className="input w-full sm:w-28" value={params.contract}
                onChange={(e) => setParam({ contract: e.target.value as "sale" | "rent" })}>
                <option value="sale">🏠 Buy</option>
                <option value="rent">🔑 Rent</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">City *</label>
              <input className="input w-full sm:w-40" placeholder="e.g. Milano"
                value={params.city} onChange={(e) => setParam({ city: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted" title="Idealista needs the province; leave empty if the city is a province capital">
                Province
              </label>
              <input className="input w-full sm:w-32" placeholder="(optional)"
                value={params.province} onChange={(e) => setParam({ province: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted"
                title="Neighborhood, best-effort: open the generated URLs to check the portal recognises it">
                Zone
              </label>
              <input className="input w-full sm:w-32" placeholder="(optional)"
                value={params.zone} onChange={(e) => setParam({ zone: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Min €</label>
              <input className="input w-full sm:w-24" type="number" value={params.min_price}
                onChange={(e) => setParam({ min_price: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Max €</label>
              <input className="input w-full sm:w-24" type="number" value={params.max_price}
                onChange={(e) => setParam({ max_price: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Min rooms</label>
              <select className="input w-full sm:w-24" value={params.min_rooms}
                onChange={(e) => setParam({ min_rooms: e.target.value })}>
                <option value="">Any</option>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}+</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs t-muted">Min sqm</label>
              <input className="input w-full sm:w-20" type="number" value={params.min_sqm}
                onChange={(e) => setParam({ min_sqm: e.target.value })} />
            </div>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder="Profile name (optional)"
              value={name} onChange={(e) => setName(e.target.value)} />
            <input className="input w-full" placeholder="Extra excluded keywords (optional, comma-separated)"
              value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </div>
          <GlobalKeywordsHint settings={settings} />

          {!built && (
            <button className="btn-primary" onClick={generate} disabled={!params.city.trim()}>
              Generate search URLs
            </button>
          )}

          {built && (
            <div className="space-y-2 pt-1">
              <p className="text-xs t-muted">
                Check the generated searches (open them to verify the results),
                then create the profiles:
              </p>
              {(["immobiliare", "idealista"] as const).map((portal) => (
                <label key={portal}
                  className="flex items-center gap-3 p-2.5 rounded-xl panel cursor-pointer">
                  <input type="checkbox" checked={usePortals[portal]}
                    onChange={(e) =>
                      setUsePortals((u) => ({ ...u, [portal]: e.target.checked }))} />
                  <PortalBadge portal={portal} />
                  <span className="text-xs t-muted truncate flex-1">{built[portal]}</span>
                  <a href={built[portal]} target="_blank" rel="noreferrer"
                    className="accent-link text-xs shrink-0"
                    onClick={(e) => e.stopPropagation()}>
                    Open ↗
                  </a>
                </label>
              ))}
              {error && <p className="accent-bad text-xs">{error}</p>}
              <button className="btn-primary" onClick={createFromBuilder}
                disabled={saving || (!usePortals.immobiliare && !usePortals.idealista)}>
                {saving ? "Saving…" : editingId !== null ? "Save changes" : "Create profiles"}
              </button>
            </div>
          )}
          {!built && error && <p className="accent-bad text-xs">{error}</p>}
        </div>
      )}

      {profiles.length === 0 && mode === "closed" && (
        <p className="text-sm t-muted">
          No search profiles configured. Build a search with your criteria or
          paste a results URL from Immobiliare.it / Idealista to get started.
        </p>
      )}

      {profiles.length > 1 && (
        <div className="flex flex-wrap items-center gap-2 mb-2 px-1">
          <label className="flex items-center gap-2 text-xs t-muted cursor-pointer">
            <input type="checkbox" checked={allSelected}
              // "some but not all" deserves its own tick: without it, the box
              // reads as "nothing selected" while a bulk bar is on screen
              ref={(el) => {
                if (el) el.indeterminate = selected.size > 0 && !allSelected;
              }}
              onChange={() => setSelected(
                allSelected ? new Set() : new Set(profiles.map((p) => p.id)),
              )} />
            Select all
          </label>
          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs chip-blue px-2 py-1 rounded-lg font-medium">
                {selected.size} selected
              </span>
              <button className="btn-ghost !text-xs" disabled={bulkBusy}
                onClick={() => runBulk([...selected], "activate")}>
                ▶️ Activate
              </button>
              <button className="btn-ghost !text-xs" disabled={bulkBusy}
                onClick={() => runBulk([...selected], "pause")}>
                ⏸️ Pause
              </button>
              {/* value stays on the placeholder: this is an action, not a state
                  — the selection can hold searches with different channels */}
              <select className="input !py-1 !px-2 text-xs w-full sm:w-48"
                value="" disabled={bulkBusy}
                onChange={(e) =>
                  runBulk([...selected], "notify", e.target.value)}>
                <option value="" disabled>Notifications →</option>
                {channelOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <button
                className="btn-ghost !text-xs hover:!text-rose-500"
                disabled={bulkBusy}
                onClick={() => askDelete(selectedProfiles)}>
                🗑 Delete
              </button>
              <button className="text-xs accent-link"
                onClick={() => setSelected(new Set())}>
                Clear
              </button>
            </div>
          )}
        </div>
      )}

      <ul className="space-y-2">
        {profiles.map((p) => {
          const badge = statusBadge[p.last_run_status];
          const channel = channelOptions.find((o) => o.value === p.notify_channels)
            ?? channelOptions[0];
          return (
            <li key={p.id}
              className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel">
              {profiles.length > 1 && (
                <input type="checkbox" className="shrink-0"
                  aria-label={`Select ${p.name}`}
                  checked={selected.has(p.id)}
                  onChange={() => toggleOne(p.id)} />
              )}
              <PortalBadge portal={p.portal} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm truncate">{p.name}</p>
                <p className="text-xs t-dim truncate">{p.search_url}</p>
                {p.params && (p.params.city || p.params.min_price || p.params.max_price || p.params.min_rooms || p.params.min_sqm || p.params.zone) && (
                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                    {p.params.contract && (
                      <span className="text-[11px] chip-blue px-2 py-0.5 rounded-md font-medium">
                        {p.params.contract === "rent" ? "🔑 Rent" : "🏠 Buy"}
                      </span>
                    )}
                    {p.params.city && (
                      <span className="text-[11px] chip-emerald px-2 py-0.5 rounded-md font-medium">
                        📍 {p.params.city}{p.params.province ? ` (${p.params.province})` : ""}
                        {p.params.zone ? ` · ${p.params.zone}` : ""}
                      </span>
                    )}
                    {(p.params.min_price || p.params.max_price) && (
                      <span className="text-[11px] chip-amber px-2 py-0.5 rounded-md font-medium">
                        💰 {p.params.min_price ? `${p.params.min_price.toLocaleString("it-IT")} €` : "0 €"} – {p.params.max_price ? `${p.params.max_price.toLocaleString("it-IT")} €` : "∞"}
                      </span>
                    )}
                    {(p.params.min_rooms || p.params.max_rooms) && (
                      <span className="text-[11px] chip-blue px-2 py-0.5 rounded-md font-medium">
                        🛏️ {p.params.min_rooms ?? 1}{p.params.max_rooms ? `–${p.params.max_rooms}` : "+"} rooms
                      </span>
                    )}
                    {p.params.min_sqm && (
                      <span className="text-[11px] chip-emerald px-2 py-0.5 rounded-md font-medium">
                        📐 ≥ {p.params.min_sqm} sqm
                      </span>
                    )}
                  </div>
                )}
                {p.last_run_detail && (
                  <p className="text-xs t-muted mt-0.5">{p.last_run_detail}</p>
                )}
                {combinedKeywords(p, settings).length > 0 && (
                  <p className="text-xs t-dim mt-0.5 truncate"
                    title="Listings mentioning any of these words are discarded (Settings + this search's own extras)">
                    🚫 Excludes: {combinedKeywords(p, settings).join(", ")}
                  </p>
                )}
                {/* a selected-but-unconfigured channel silently drops alerts:
                    make that state impossible to miss */}
                {!channel.ok && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                    ⚠️ {channel.warn}
                  </p>
                )}
              </div>
              {badge && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${badge.cls}`}>
                  {badge.label}
                  {/* a streak, unlike a single 403, means the scraper is
                      really broken — the same signal that triggers the alert */}
                  {p.consecutive_failures > 1 && ` ×${p.consecutive_failures}`}
                </span>
              )}
              <select
                className="input !py-1 !px-2 text-xs w-44"
                title="Where to send notifications for this search"
                value={p.notify_channels}
                onChange={(e) => runBulk([p.id], "notify", e.target.value)}>
                {channelOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
                <input type="checkbox" checked={p.is_active}
                  onChange={() =>
                    runBulk([p.id], p.is_active ? "pause" : "activate")} />
                Active
              </label>
              <button className="t-dim hover:opacity-70 transition text-sm btn-focus
                  inline-flex items-center justify-center w-9 h-9 sm:w-auto sm:h-auto
                  rounded-lg shrink-0"
                title="Edit this search profile" aria-label="Edit this search profile"
                onClick={() => editProfile(p)}>
                ✏️
              </button>
              <button className="t-dim hover:text-rose-500 transition text-sm btn-focus
                  inline-flex items-center justify-center w-9 h-9 sm:w-auto sm:h-auto
                  rounded-lg shrink-0"
                title="Delete this search profile" aria-label="Delete this search profile"
                onClick={() => askDelete([p])}>
                🗑
              </button>
            </li>
          );
        })}
      </ul>

      {/* portaled to <body>: this section is a .glass, and its backdrop-blur
          makes it the containing block of any `fixed` descendant — the overlay
          would cover the panel instead of the viewport (the other modals live
          in App.tsx, outside any .glass, so they never hit this) */}
      {deleting && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
          onClick={() => !deleteBusy && setDeleting(null)}>
          <div className="glass rounded-2xl max-w-md w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold mb-2">
              {deleting.length === 1
                ? `Delete “${deleting[0].name}”?`
                : `Delete ${deleting.length} searches?`}
            </h2>
            <p className="text-sm t-muted">
              {deleting.length === 1 ? "The search stops" : "The searches stop"}{" "}
              being monitored. Their results are already in the dashboard — you
              choose whether they go too.
            </p>
            {deleting.length > 1 && (
              <ul className="mt-2 text-xs t-muted space-y-0.5 max-h-32 overflow-y-auto">
                {deleting.map((p) => <li key={p.id} className="truncate">· {p.name}</li>)}
              </ul>
            )}

            <div className="mt-4 p-3 rounded-xl panel text-sm">
              {results === null && !deleteError && (
                <p className="t-muted">Counting the results…</p>
              )}
              {results && results.tracked === 0 && (
                <p className="t-muted">
                  No property in the dashboard is attributable to{" "}
                  {deleting.length === 1 ? "this search" : "these searches"}, so
                  “delete the results too” has nothing to delete. Results are
                  attributed from the scans that found them: a search deleted
                  before it has run keeps nothing on record.
                </p>
              )}
              {results && results.tracked > 0 && (
                <>
                  <p>
                    {deleting.length === 1 ? "It found" : "They found"}{" "}
                    <strong>{results.tracked}</strong>{" "}
                    {results.tracked === 1 ? "property" : "properties"};{" "}
                    <strong>{results.deletable}</strong> would be deleted.
                  </p>
                  {/* the spared ones are the whole reason this dialog shows
                      numbers rather than just asking yes/no */}
                  {(results.kept_shared > 0 || results.kept_curated > 0) && (
                    <ul className="mt-2 space-y-0.5 text-xs t-muted">
                      {results.kept_shared > 0 && (
                        <li>
                          · {results.kept_shared} kept: also found by a search
                          you are keeping
                        </li>
                      )}
                      {results.kept_curated > 0 && (
                        <li>
                          · {results.kept_curated} kept: favorited or annotated
                          by you
                        </li>
                      )}
                    </ul>
                  )}
                  {results.deletable > 0 && (
                    <p className="mt-2 text-xs accent-bad">
                      Deleting them is irreversible: price history included.
                    </p>
                  )}
                </>
              )}
            </div>

            {deleteError && <p className="accent-bad text-xs mt-3">{deleteError}</p>}

            <div className="flex flex-wrap gap-2 mt-5">
              <button className="btn-ghost" disabled={deleteBusy}
                onClick={() => setDeleting(null)}>
                Cancel
              </button>
              <button className="btn-ghost flex-1" disabled={deleteBusy}
                onClick={() => confirmDelete(false)}>
                Keep the results
              </button>
              <button className="btn-primary flex-1 !bg-rose-600 hover:!bg-rose-700"
                disabled={deleteBusy || !results || results.deletable === 0}
                onClick={() => confirmDelete(true)}>
                {deleteBusy ? "Deleting…" : `Delete with ${results?.deletable ?? 0} ${
                  results?.deletable === 1 ? "property" : "properties"}`}
              </button>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </section>
  );
}
