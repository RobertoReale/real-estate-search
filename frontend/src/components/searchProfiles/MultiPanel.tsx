/** Mode "multi": one query understood as several searches, reviewed as a list
 * before any of them is created. Dropping an alternative here is cheaper than
 * deleting the profile afterwards. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { PortalBadge } from "../PortalBadge";
import { GlobalKeywordsHint } from "./helpers";
import { Button, Checkbox, Chip, IconButton, Input } from "../../ui";
import { Close, External, Hint, Warning } from "../../ui/icons";

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
            <Chip tone="accent" className="uppercase">
              {t("profiles.searchNumber", { n: idx + 1 })}
            </Chip>
            {search.interpretation.map((part) => (
              <Chip key={part} tone="positive" size="md">{part}</Chip>
            ))}
            <button data-action="profiles.multi.edit" className="text-xs accent-link ml-auto"
              title={t("profiles.editInBuilder")}
              onClick={() => editInBuilder(search)}>
              {t("common.edit")}
            </button>
            <IconButton data-action="profiles.multi.drop" variant="ghost" tone="negative" size="sm"
              label={t("profiles.dropAlternative")}
              onClick={() => setMulti((m) => m.filter((_, i) => i !== idx))}>
              <Close size={14} />
            </IconButton>
          </div>
          {search.notes.map((note) => (
            <p key={note} className="flex items-start gap-1.5 text-xs t-muted">
              <Hint className="shrink-0 mt-0.5" /> {note}
            </p>
          ))}
          {search.warnings.map((warning) => (
            <p key={warning}
              className="flex items-start gap-1.5 text-xs text-caution-ink">
              <Warning className="shrink-0 mt-0.5" /> {warning}
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
                  className="inline-flex items-center gap-1 accent-link shrink-0">
                  {t("modal.open")} <External />
                </a>
              </div>
            );
          })}
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-3">
        {(["immobiliare", "idealista"] as const).map((portal) => (
          <Checkbox key={portal} data-action="profiles.multi.usePortal"
            checked={usePortals[portal]}
            onCheckedChange={(v) =>
              setUsePortals((u) => ({ ...u, [portal]: v === true }))}
            label={portal} />
        ))}
        <Input data-action="profiles.multi.keywords"
          className="flex-1 basis-full sm:basis-auto sm:min-w-[14rem]"
          aria-label={t("profiles.keywordsPlaceholder")}
          placeholder={t("profiles.keywordsPlaceholder")}
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      </div>
      <GlobalKeywordsHint settings={settings} />
      {error && <p className="accent-bad text-xs">{error}</p>}
      <Button data-action="profiles.multi.create" variant="solid" tone="accent" onClick={createFromMulti}
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
      </Button>
    </div>
  );
}
