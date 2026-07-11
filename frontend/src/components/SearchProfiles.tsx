import { useState } from "react";
import { api } from "../services/api";
import { PortalBadge } from "./PortalBadge";
import type {
  AssistantSearch, SearchBuilderParams, SearchBuilderUrls, SearchProfile,
  Settings,
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
  ];

  const setParam = (patch: Partial<SearchBuilderParams>) => {
    setParams((p) => ({ ...p, ...patch }));
    setBuilt(null); // generated URLs are stale as soon as an input changes
    // a warning like "I could not tell which city" is answered by the very
    // edit the user is making: keeping it on screen would be nagging
    setAssistant((a) => (a && a.warnings.length ? { ...a, warnings: [] } : a));
  };

  function resetForm() {
    setName(""); setUrl(""); setKeywords(""); setError("");
    setParams(EMPTY_BUILDER); setBuilt(null);
    setQuery(""); setAssistant(null); setMulti([]);
    setMode("closed");
  }

  function editInBuilder(search: AssistantSearch) {
    setAssistant(search);
    setParams(paramsFromAssistant(search));
    // the assistant only returns URLs when it recognised a city; otherwise
    // the builder opens pre-filled and waits for the missing piece
    setBuilt(search.urls);
    setMode("builder");
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

  async function createFromMulti() {
    setSaving(true);
    setError("");
    try {
      for (const search of multi) {
        if (!search.urls) continue; // no city recognised: cannot build URLs
        for (const portal of ["immobiliare", "idealista"] as const) {
          if (!usePortals[portal]) continue;
          await api.createProfile({
            name: `${searchLabel(search)} (${portal})`,
            search_url: search.urls[portal],
            excluded_keywords: keywords,
            is_active: true,
          });
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

  async function submitUrl() {
    setSaving(true);
    setError("");
    try {
      await api.createProfile({
        name: name || "Untitled search",
        search_url: url,
        excluded_keywords: keywords,
        is_active: true,
      });
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
      for (const portal of ["immobiliare", "idealista"] as const) {
        if (!usePortals[portal]) continue;
        await api.createProfile({
          name: `${label} (${portal})`,
          search_url: built[portal],
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

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold text-base">
          🔍 Monitored searches{" "}
          <span className="t-muted text-sm">({profiles.length})</span>
        </h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost"
            onClick={() => setMode(mode === "assistant" ? "closed" : "assistant")}>
            {mode === "assistant" ? "Cancel" : "💬 Just describe it"}
          </button>
          <button className="btn-ghost"
            onClick={() => setMode(mode === "builder" ? "closed" : "builder")}>
            {mode === "builder" ? "Cancel" : "🧭 Build a search"}
          </button>
          <button className="btn-ghost"
            onClick={() => setMode(mode === "url" ? "closed" : "url")}>
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
          <input className="input w-full"
            placeholder="https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000…"
            value={url} onChange={(e) => setUrl(e.target.value)} />
          {error && <p className="accent-bad text-xs">{error}</p>}
          <button className="btn-primary" onClick={submitUrl} disabled={saving || !url}>
            {saving ? "Saving…" : "Save profile"}
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
                {saving ? "Saving…" : "Create profiles"}
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

      <ul className="space-y-2">
        {profiles.map((p) => {
          const badge = statusBadge[p.last_run_status];
          const channel = channelOptions.find((o) => o.value === p.notify_channels)
            ?? channelOptions[0];
          return (
            <li key={p.id}
              className="flex flex-wrap items-center gap-3 p-3 rounded-xl panel">
              <PortalBadge portal={p.portal} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-sm truncate">{p.name}</p>
                <p className="text-xs t-dim truncate">{p.search_url}</p>
                {p.last_run_detail && (
                  <p className="text-xs t-muted mt-0.5">{p.last_run_detail}</p>
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
                onChange={async (e) => {
                  await api.updateProfile(p.id, { ...p, notify_channels: e.target.value });
                  onChanged();
                }}>
                {channelOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <label className="flex items-center gap-1.5 text-xs t-muted cursor-pointer">
                <input type="checkbox" checked={p.is_active}
                  onChange={async () => {
                    await api.updateProfile(p.id, { ...p, is_active: !p.is_active });
                    onChanged();
                  }} />
                Active
              </label>
              <button className="t-dim hover:text-rose-500 transition text-sm btn-focus
                  inline-flex items-center justify-center w-9 h-9 sm:w-auto sm:h-auto
                  rounded-lg shrink-0"
                title="Delete this search profile" aria-label="Delete this search profile"
                onClick={async () => {
                  if (confirm(`Delete profile "${p.name}"?`)) {
                    await api.deleteProfile(p.id);
                    onChanged();
                  }
                }}>
                🗑
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
