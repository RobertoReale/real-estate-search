/** Mode "multi": one query understood as several searches, reviewed as a list
 * before any of them is created. Dropping an alternative here is cheaper than
 * deleting the profile afterwards. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { PortalBadge } from "../PortalBadge";
import { GlobalKeywordsHint } from "./helpers";

export function MultiPanel({ sp }: { sp: SearchProfilesState }) {
  const { t, settings, multi, setMulti, setMode, usePortals, setUsePortals, keywords, setKeywords,
    editInBuilder, createFromMulti, saving, error } = sp;
  return (
    <div className="mb-4 p-4 rounded-xl panel space-y-3">
      <div className="flex items-center gap-2">
        <p className="text-xs t-muted flex-1">
          {t("profiles.multiIntro", { count: multi.length })}
        </p>
        <button data-action="profiles.multi.reword" className="text-xs accent-link"
          onClick={() => setMode("assistant")}>
          {t("profiles.reword")}
        </button>
      </div>
      {multi.map((search, idx) => (
        <div key={idx} className="p-3 rounded-xl panel space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-3xs font-bold uppercase px-2 py-0.5 rounded chip-accent">
              {t("profiles.searchNumber", { n: idx + 1 })}
            </span>
            {search.interpretation.map((part) => (
              <span key={part}
                className="text-xs chip-positive px-2 py-1 rounded-lg font-medium">
                {part}
              </span>
            ))}
            <button data-action="profiles.multi.edit" className="text-xs accent-link ml-auto"
              title={t("profiles.editInBuilder")}
              onClick={() => editInBuilder(search)}>
              {t("common.edit")}
            </button>
            <button data-action="profiles.multi.drop" className="t-dim hover:text-negative-ink transition text-xs btn-focus"
              title={t("profiles.dropAlternative")}
              aria-label={t("profiles.dropAlternative")}
              onClick={() => setMulti((m) => m.filter((_, i) => i !== idx))}>
              ✕
            </button>
          </div>
          {search.notes.map((note) => (
            <p key={note} className="text-xs t-muted">ℹ️ {note}</p>
          ))}
          {search.warnings.map((warning) => (
            <p key={warning}
              className="text-xs text-caution-ink">
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
                  {t("modal.open")}
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
            <input data-action="profiles.multi.usePortal" type="checkbox" checked={usePortals[portal]}
              onChange={(e) =>
                setUsePortals((u) => ({ ...u, [portal]: e.target.checked }))} />
            {portal}
          </label>
        ))}
        <input data-action="profiles.multi.keywords" className="input flex-1 basis-full sm:basis-auto sm:min-w-[14rem]"
          placeholder={t("profiles.keywordsPlaceholder")}
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      </div>
      <GlobalKeywordsHint settings={settings} />
      {error && <p className="accent-bad text-xs">{error}</p>}
      <button data-action="profiles.multi.create" className="btn-primary" onClick={createFromMulti}
        disabled={
          saving
          || multi.every((s) => !s.urls)
          || (!usePortals.immobiliare && !usePortals.idealista)
        }>
        {saving
          ? t("common.saving")
          : t("profiles.createProfiles", {
              count:
                multi.filter((s) => s.urls).length *
                (Number(usePortals.immobiliare) + Number(usePortals.idealista)),
            })}
      </button>
    </div>
  );
}
