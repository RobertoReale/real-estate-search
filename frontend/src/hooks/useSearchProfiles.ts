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
import { api } from "../services/api";
import type {
  AssistantSearch, ProfileResults, SearchBuilderParams, SearchBuilderUrls,
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

export function useSearchProfiles({ profiles, settings, onChanged }: UseSearchProfilesArgs) {
  const t = useT();
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
  const [editingGroupIds, setEditingGroupIds] = useState<number[]>([]);

  // builder state
  const [params, setParams] = useState<SearchBuilderParams>(EMPTY_BUILDER);
  const [built, setBuilt] = useState<SearchBuilderUrls | null>(null);
  const [generating, setGenerating] = useState(false);
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

  async function groupSelected(targets: SearchProfile[]) {
    if (targets.length < 2) return;
    const defaultName = getBaseName(targets[0].name || t("profiles.defaultName"));
    const newBaseName = window.prompt(t("profiles.mergePrompt"), defaultName);
    if (!newBaseName || !newBaseName.trim()) return;
    const cleaned = getBaseName(newBaseName.trim());
    setBulkBusy(true);
    setError("");
    try {
      for (const p of targets) {
        await api.updateProfile(p.id, {
          name: `${cleaned} (${p.portal})`,
        });
      }
      setSelected(new Set());
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBulkBusy(false);
    }
  }

  async function separateGroup(group: GroupedSearchProfile) {
    if (group.profiles.length < 2) return;
    if (!window.confirm(t("profiles.separateConfirm", { name: group.baseName }))) return;
    setBulkBusy(true);
    setError("");
    try {
      for (const p of group.profiles) {
        await api.updateProfile(p.id, {
          name: `${group.baseName} - ${p.portal.toUpperCase()}`,
        });
      }
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
      setBuilt({
        immobiliare: imm?.search_url || "",
        idealista: ideal?.search_url || "",
      });
      setUsePortals({
        immobiliare: Boolean(imm) || true,
        idealista: Boolean(ideal) || true,
      });
      setMode("builder");
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
      setError(e instanceof Error ? e.message : t("common.unknownError"));
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
      setError(e instanceof Error ? e.message : t("common.unknownError"));
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
            name: `${searchLabel(search, t)} (${portal})`,
            search_url: search.urls[portal],
            excluded_keywords: keywords,
            is_active: true,
          });
          addedCount++;
        }
      }
      if (addedCount === 0 && multi.some(s => s.urls)) {
        setError(t("profiles.allAlreadyPresent"));
      } else {
        resetForm();
        onChanged();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
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
        setError(t("profiles.duplicateExists", { name: dup.name }));
        setSaving(false);
        return;
      }
      if (editingId !== null) {
        const current = profiles.find((p) => p.id === editingId);
        await api.updateProfile(editingId, {
          name: name || t("profiles.untitled"),
          search_url: url,
          excluded_keywords: keywords,
          notify_channels: current?.notify_channels ?? "",
          is_active: current?.is_active ?? true,
        });
      } else {
        await api.createProfile({
          name: name || t("profiles.untitled"),
          search_url: url,
          excluded_keywords: keywords,
          is_active: true,
        });
      }
      resetForm();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setSaving(false);
    }
  }

  async function generate() {
    setError("");
    setGenerating(true);
    try {
      // verify=true: with a zone this asks Idealista once whether it knows the
      // slug, so the URL we save is the precise zone page when one exists
      setBuilt(await api.buildSearchUrls(params, true));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setGenerating(false);
    }
  }

  async function createFromBuilder() {
    if (!built) return;
    setSaving(true);
    setError("");
    const label = name || [
      t(params.contract === "rent" ? "profiles.labelRent" : "profiles.labelBuy"),
      params.city,
      params.zone,
    ].filter(Boolean).join(" · ");
    try {
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
                setSaving(false);
                return;
              }
              await api.updateProfile(existingForPortal.id, {
                name: `${name || label} (${portal})`,
                search_url: targetUrl,
                excluded_keywords: keywords,
                notify_channels: existingForPortal.notify_channels ?? firstCurrent.notify_channels ?? "",
                is_active: existingForPortal.is_active ?? firstCurrent.is_active ?? true,
              });
            } else {
              if (!findDuplicateProfile(targetUrl, keywords)) {
                await api.createProfile({
                  name: `${name || label} (${portal})`,
                  search_url: targetUrl,
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
          setError(t("profiles.duplicateParams"));
          setSaving(false);
          return;
        }
      }
      resetForm();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setSaving(false);
    }
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
