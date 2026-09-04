/** Everything the search-profile panel does, minus how it looks.
 *
 * The panel is one state machine with five modes (closed / url / builder /
 * assistant / multi) and a set of mutations that all end the same way: reset the
 * form and tell the parent to refetch. Keeping that here leaves the components
 * as views, and makes the awkward parts — which mode an edit opens in, what
 * counts as a duplicate, which portals a save touches — readable in one place
 * instead of interleaved with 700 lines of JSX.
 *
 * Returned as one object that the subcomponents destructure: they are views over
 * this single machine, not independently reusable widgets, and threading twenty
 * props through each of them would only obscure that.
 */

import { useState } from "react";
import { useT } from "../i18n";
import {
  useAskAssistant, useBulkProfiles, useBuildSearchUrls, useParseSearchUrl,
  useProfileResults, useRenameProfiles, useSaveProfiles, type ProfileWrite,
} from "../queries/searchProfiles";
import type {
  AssistantSearch, SearchBuilderParams, SearchBuilderUrls,
  GroupedSearchProfile, SearchProfile, Settings,
} from "../types";
import { getBaseName, groupSearchProfiles } from "../utils/searchProfiles";
import { EMPTY_BUILDER } from "../components/searchProfiles/constants";
import {
  channelReadiness, paramsFromAssistant, paramsFromProfile, searchLabel,
} from "../components/searchProfiles/helpers";

export interface UseSearchProfilesArgs {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void;
}

/** A URL pair this hook assembled itself, out of what a stored profile already
 *  holds, rather than one the backend built.
 *
 *  The provenance fields go with it and they are not padding: only the backend
 *  can say whether Idealista confirmed a zone slug or which filters its URL
 *  grammar dropped, so a locally-assembled pair claims neither. `false` and the
 *  empty lists are what "not verified" reads as in the form — the same thing it
 *  showed before these fields were typed, now said out loud. `generate` replaces
 *  it with the real answer the moment the user presses the button. */
function unverifiedUrls(immobiliare: string, idealista: string): SearchBuilderUrls {
  return {
    immobiliare, idealista,
    idealista_zone_page: false, idealista_unsupported: [], zone_warnings: [],
  };
}

export function useSearchProfiles({ profiles, settings, onChanged }: UseSearchProfilesArgs) {
  const t = useT();
  const [mode, setMode] = useState<
    "closed" | "url" | "builder" | "assistant" | "multi"
  >("closed");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [keywords, setKeywords] = useState("");
  const [error, setError] = useState("");
  // set while editing an existing profile via the "url" form, so submitUrl
  // knows whether to PUT over it instead of POSTing a new one
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingGroupIds, setEditingGroupIds] = useState<number[]>([]);

  // builder state
  const [params, setParams] = useState<SearchBuilderParams>(EMPTY_BUILDER);
  const [built, setBuilt] = useState<SearchBuilderUrls | null>(null);
  const [usePortals, setUsePortals] = useState({ immobiliare: true, idealista: true });

  // assistant state: the parsed read-back stays visible in the builder, so
  // the user can see what the sentence was understood to mean
  const [query, setQuery] = useState("");
  const [assistant, setAssistant] = useState<AssistantSearch | null>(null);
  // a query with "o"/"oppure" yields several alternatives, reviewed as a list
  const [multi, setMulti] = useState<AssistantSearch[]>([]);

  // delete dialog: the searches awaiting confirmation (one row, or a whole
  // selection), plus what their results would cost — fetched on open, for the
  // set as a whole, since "kept: another search covers it" only counts searches
  // that survive the delete
  const [deleting, setDeleting] = useState<SearchProfile[] | null>(null);
  const [deleteFailure, setDeleteFailure] = useState("");

  // bulk selection: acting on every search one row at a time is the tedium this
  // exists to remove (pausing them all before a holiday, muting a noisy set…)
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const bulkProfiles = useBulkProfiles();
  const renameProfiles = useRenameProfiles();
  const saveProfiles = useSaveProfiles();
  // Two instances of the same mutation, and the split is deliberate: the
  // button's "Generating…" belongs to the press, not to the silent re-derivation
  // that fills the other portal's slot when an existing search is opened.
  const buildUrls = useBuildSearchUrls();
  const prefillUrls = useBuildSearchUrls();
  const parseUrl = useParseSearchUrl();
  const askAssistant = useAskAssistant();
  // The counts arrive after the dialog does (`results === null` is the loading
  // state): the question is worth asking even while they load.
  const deleteResults = useProfileResults(deleting?.map((p) => p.id) ?? null);
  const results = deleteResults.data ?? null;
  // Merging, separating and a bulk action all write the same rows, so one flag
  // over the three of them is what keeps a second press out while any is in
  // flight.
  const bulkBusy = bulkProfiles.isPending || renameProfiles.isPending;
  const deleteBusy = bulkProfiles.isPending;
  const saving = saveProfiles.isPending;
  const generating = buildUrls.isPending;
  const asking = askAssistant.isPending;
  // The dialog reports two different failures in one line: the counts it could
  // not fetch, and the delete it could not carry out.
  const deleteError = deleteFailure
    || (deleteResults.error ? String(deleteResults.error.message) : "");

  const ready = channelReadiness(settings);
  const channelOptions = [
    {
      value: "",
      label: t("profiles.chAll"),
      ok: ready.telegram || ready.email,
      warn: t("profiles.chAllWarn"),
    },
    {
      value: "telegram",
      label: t(ready.telegram ? "profiles.chTelegram" : "profiles.chTelegramOff"),
      ok: ready.telegram,
      warn: t("profiles.chTelegramWarn"),
    },
    {
      value: "email",
      label: t(ready.email ? "profiles.chEmail" : "profiles.chEmailOff"),
      ok: ready.email,
      warn: t("profiles.chEmailWarn"),
    },
    {
      // silence is a choice, not a misconfiguration: keep the search running
      // and its cards flowing into the dashboard, just never get pinged for it
      value: "none",
      label: t("profiles.chNone"),
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

  function toggleGroup(ids: number[]) {
    setSelected((s) => {
      const next = new Set(s);
      const allIn = ids.every((id) => next.has(id));
      if (allIn) {
        ids.forEach((id) => next.delete(id));
      } else {
        ids.forEach((id) => next.add(id));
      }
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
    setError("");
    try {
      await bulkProfiles.mutateAsync({ ids, action, notifyChannels });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function groupSelected(targets: SearchProfile[]) {
    if (targets.length < 2) return;
    const defaultName = getBaseName(targets[0].name || t("profiles.defaultName"));
    const newBaseName = window.prompt(t("profiles.mergePrompt"), defaultName);
    if (!newBaseName || !newBaseName.trim()) return;
    const cleaned = getBaseName(newBaseName.trim());
    setError("");
    try {
      await renameProfiles.mutateAsync(
        targets.map((p) => ({ profile: p, name: `${cleaned} (${p.portal})` })));
      setSelected(new Set());
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function separateGroup(group: GroupedSearchProfile) {
    if (group.profiles.length < 2) return;
    if (!window.confirm(t("profiles.separateConfirm", { name: group.baseName }))) return;
    setError("");
    try {
      // A plain space before the portal, and this is the whole point of the
      // button. `getBaseName` strips a trailing portal preceded by a bracket or
      // a dash — which is how a merged pair is recognised as one search — so
      // the `<base> - PORTAL` this used to write was stripped straight back off
      // and the two rows folded together again the moment they were separated.
      // Separating has to produce names the grouping will not undo.
      await renameProfiles.mutateAsync(
        group.profiles.map((p) => ({ profile: p, name: `${group.baseName} ${p.portal}` })));
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const setParam = (patch: Partial<SearchBuilderParams>) => {
    setParams((p) => ({ ...p, ...patch }));
    setBuilt(null); // generated URLs are stale as soon as an input changes
    // a warning like "I could not tell which city" is answered by the very
    // edit the user is making: keeping it on screen would be nagging
    setAssistant((a) => (a && a.warnings.length ? { ...a, warnings: [] } : a));
  };

  /** Opens the delete dialog. Naming the searches is what starts the query for
   *  what their results amount to, so the dialog is on screen while it loads. */
  function askDelete(targets: SearchProfile[]) {
    setDeleteFailure("");
    setDeleting(targets);
  }

  async function confirmDelete(alsoDeleteResults: boolean) {
    if (!deleting) return;
    setDeleteFailure("");
    try {
      await bulkProfiles.mutateAsync({
        ids: deleting.map((p) => p.id),
        action: "delete",
        deleteResults: alsoDeleteResults,
      });
      setDeleting(null);
      setSelected(new Set());
      onChanged();
    } catch (e) {
      setDeleteFailure(e instanceof Error ? e.message : String(e));
    }
  }

  function resetForm() {
    setName(""); setUrl(""); setKeywords(""); setError("");
    setParams(EMPTY_BUILDER); setBuilt(null);
    setQuery(""); setAssistant(null); setMulti([]);
    setEditingId(null);
    setEditingGroupIds([]);
    setMode("closed");
  }

  function editProfile(p: SearchProfile) {
    setName(p.name);
    setUrl(p.search_url);
    setKeywords(p.excluded_keywords);
    setEditingId(p.id);
    setEditingGroupIds([p.id]);
    setError("");
    if (p.params && (p.params.city || p.params.min_price || p.params.min_rooms || p.params.zone)) {
      const formParams = paramsFromProfile(p.params);
      setParams(formParams);
      setBuilt(unverifiedUrls(
        p.portal === "immobiliare" ? p.search_url : "",
        p.portal === "idealista" ? p.search_url : "",
      ));
      setUsePortals({
        immobiliare: p.portal === "immobiliare",
        idealista: p.portal === "idealista",
      });
      setMode("builder");
      // the profile only carries its own portal's URL; fill in the other
      // portal's slot too, so ticking its checkbox has a URL to save instead
      // of silently no-opping (createFromBuilder skips an empty built[portal])
      prefillUrls.mutate({ params: formParams, verify: false }, {
        onSuccess: (urls) => setBuilt((b) => b && {
          ...urls,
          immobiliare: b.immobiliare || urls.immobiliare,
          idealista: b.idealista || urls.idealista,
        }),
        // a URL we could not re-derive simply leaves that portal's slot as the
        // stored one; there is nothing for the user to do about it
        onError: () => {},
      });
    } else {
      setMode("url");
    }
  }

  function editGroup(group: GroupedSearchProfile) {
    const first = group.profiles[0];
    setName(group.baseName);
    setUrl(first.search_url);
    setKeywords(group.excluded_keywords);
    setEditingId(first.id);
    setEditingGroupIds(group.ids);
    setError("");
    const paramsProfile = group.profiles.find((p) => p.params);
    if (paramsProfile?.params && (paramsProfile.params.city || paramsProfile.params.min_price || paramsProfile.params.min_rooms || paramsProfile.params.zone)) {
      const formParams = paramsFromProfile(paramsProfile.params);
      setParams(formParams);
      const imm = group.profiles.find((p) => p.portal === "immobiliare");
      const ideal = group.profiles.find((p) => p.portal === "idealista");
      setBuilt(unverifiedUrls(imm?.search_url || "", ideal?.search_url || ""));
      setUsePortals({
        immobiliare: Boolean(imm) || true,
        idealista: Boolean(ideal) || true,
      });
      setMode("builder");
      prefillUrls.mutate({ params: formParams, verify: false }, {
        onSuccess: (urls) => setBuilt((b) => b && {
          ...urls,
          immobiliare: b.immobiliare || urls.immobiliare,
          idealista: b.idealista || urls.idealista,
        }),
        // a URL we could not re-derive simply leaves that portal's slot as the
        // stored one; there is nothing for the user to do about it
        onError: () => {},
      });
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
      const extracted = await parseUrl.mutateAsync(url);
      setParams(paramsFromProfile(extracted));
      setBuilt(unverifiedUrls(
        url.includes("immobiliare.it") ? url : "",
        url.includes("idealista.it") ? url : "",
      ));
      setUsePortals({
        immobiliare: url.includes("immobiliare.it"),
        idealista: url.includes("idealista.it"),
      });
      setMode("builder");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    }
  }

  async function ask() {
    if (!query.trim()) return;
    setError("");
    try {
      const result = await askAssistant.mutateAsync(query);
      // The backend answers `{"searches": []}` for a query that splits into
      // nothing but separators (";", "x o", …): `parse_query` skips every blank
      // segment and has nothing left to describe. `searches[0]` was then
      // `undefined` and `editInBuilder` threw, so the box replied with a raw
      // "Cannot read properties of undefined" where a plain "say more" belongs.
      const [first] = result.searches;
      if (!first) {
        setError(t("profiles.assistantNothing"));
      } else if (result.searches.length > 1) {
        setMulti(result.searches);
        setMode("multi");
      } else {
        editInBuilder(first);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
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

  /** Saves a set of rows as one act, or reports why there was nothing to save.
   *
   *  The writes are worked out first and sent second, deliberately: a builder
   *  save can cover two portals, and deciding halfway through that the second
   *  one is a duplicate would leave the pair half-written. */
  async function commit(writes: ProfileWrite[], nothingToDo: string) {
    if (writes.length === 0) {
      setError(nothingToDo);
      return;
    }
    setError("");
    try {
      await saveProfiles.mutateAsync(writes);
      resetForm();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    }
  }

  async function createFromMulti() {
    const writes: ProfileWrite[] = [];
    for (const search of multi) {
      if (!search.urls) continue; // no city recognised: cannot build URLs
      for (const portal of ["immobiliare", "idealista"] as const) {
        if (!usePortals[portal]) continue;
        if (findDuplicateProfile(search.urls[portal], keywords)) continue;
        writes.push({
          id: null,
          data: {
            name: `${searchLabel(search, t)} (${portal})`,
            search_url: search.urls[portal],
            excluded_keywords: keywords,
            is_active: true,
          },
        });
      }
    }
    if (writes.length === 0 && !multi.some((s) => s.urls)) {
      // nothing to save and nothing to complain about: no search in the answer
      // carried URLs at all
      resetForm();
      onChanged();
      return;
    }
    await commit(writes, t("profiles.allAlreadyPresent"));
  }

  async function submitUrl() {
    const dup = findDuplicateProfile(url, keywords, editingId !== null ? editingId : undefined);
    if (dup) {
      setError(t("profiles.duplicateExists", { name: dup.name }));
      return;
    }
    const current = editingId !== null
      ? profiles.find((p) => p.id === editingId)
      : undefined;
    await commit([{
      id: editingId,
      data: {
        name: name || t("profiles.untitled"),
        search_url: url,
        excluded_keywords: keywords,
        ...(editingId !== null
          ? {
              notify_channels: current?.notify_channels ?? "",
              is_active: current?.is_active ?? true,
            }
          : { is_active: true }),
      },
    }], t("common.unknownError"));
  }

  async function generate() {
    setError("");
    try {
      // verify=true: with a zone this asks Idealista once whether it knows the
      // slug, so the URL we save is the precise zone page when one exists
      setBuilt(await buildUrls.mutateAsync({ params, verify: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    }
  }

  async function createFromBuilder() {
    if (!built) return;
    const label = name || [
      t(params.contract === "rent" ? "profiles.labelRent" : "profiles.labelBuy"),
      params.city,
      params.zone,
    ].filter(Boolean).join(" · ");
    const writes: ProfileWrite[] = [];

    if (editingId !== null || editingGroupIds.length > 0) {
      const targetIds = editingGroupIds.length > 0 ? editingGroupIds : (editingId !== null ? [editingId] : []);
      const groupProfiles = profiles.filter((p) => targetIds.includes(p.id));
      const firstCurrent = groupProfiles[0] || profiles.find((p) => p.id === editingId);
      if (firstCurrent) {
        for (const portal of ["immobiliare", "idealista"] as const) {
          if (!usePortals[portal]) continue;
          const targetUrl = built[portal];
          if (!targetUrl) continue;
          const existingForPortal = groupProfiles.find((p) => p.portal === portal);
          if (existingForPortal) {
            const dup = findDuplicateProfile(targetUrl, keywords, existingForPortal.id);
            if (dup && !targetIds.includes(dup.id)) {
              setError(t("profiles.duplicateExists", { name: dup.name }));
              return;
            }
            writes.push({
              id: existingForPortal.id,
              data: {
                name: `${name || label} (${portal})`,
                search_url: targetUrl,
                excluded_keywords: keywords,
                notify_channels: existingForPortal.notify_channels ?? firstCurrent.notify_channels ?? "",
                is_active: existingForPortal.is_active ?? firstCurrent.is_active ?? true,
              },
            });
          } else if (!findDuplicateProfile(targetUrl, keywords)) {
            writes.push({
              id: null,
              data: {
                name: `${name || label} (${portal})`,
                search_url: targetUrl,
                excluded_keywords: keywords,
                is_active: true,
              },
            });
          }
        }
      }
      // An edit that resolves to no write is not a duplicate: every portal it
      // covers is already exactly what was asked for.
      if (writes.length === 0) {
        resetForm();
        onChanged();
        return;
      }
    } else {
      for (const portal of ["immobiliare", "idealista"] as const) {
        if (!usePortals[portal]) continue;
        if (findDuplicateProfile(built[portal], keywords)) continue;
        writes.push({
          id: null,
          data: {
            name: `${label} (${portal})`,
            search_url: built[portal],
            excluded_keywords: keywords,
            is_active: true,
          },
        });
      }
    }
    await commit(writes, t("profiles.duplicateParams"));
  }

  const groupedProfiles = groupSearchProfiles(profiles);

  return {
    profiles, settings, t,
    mode, setMode,
    name, setName, url, setUrl, keywords, setKeywords,
    error, setError, saving, editingId,
    params, setParam, setParams, built, generating, usePortals, setUsePortals,
    query, setQuery, asking, assistant, multi, setMulti,
    deleting, setDeleting, results, deleteBusy, deleteError,
    selected, setSelected, bulkBusy,
    channelOptions, selectedProfiles, allSelected, groupedProfiles,
    toggleGroup, runBulk, groupSelected, separateGroup,
    askDelete, confirmDelete, resetForm, editGroup, editInBuilder,
    extractParamsFromUrl, ask, createFromMulti, submitUrl, generate, createFromBuilder,
  };
}

export type SearchProfilesState = ReturnType<typeof useSearchProfiles>;
