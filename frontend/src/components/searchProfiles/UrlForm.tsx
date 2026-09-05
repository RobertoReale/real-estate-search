/** Mode "url": paste a portal search URL. Not a fallback — it is the most
 * powerful path, since every portal filter is honoured, including the ones the
 * builder cannot express. The form says so, deliberately. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { GlobalKeywordsHint } from "./helpers";
import { Button, Input } from "../../ui";
import { Extract } from "../../ui/icons";

export function UrlForm({ sp }: { sp: SearchProfilesState }) {
  const { t, settings, name, setName, keywords, setKeywords, url, setUrl,
    extractParamsFromUrl, submitUrl, saving, editingId, error } = sp;
  return (
    <div className="mb-4 p-4 rounded-xl panel space-y-3">
      <p className="text-xs t-muted">{t("profiles.urlIntro")}</p>
      {/* The one thing a new user must understand: pasting a URL is not a
          fallback, it is the most powerful way to search — every portal
          filter is honored, including the ones the builder cannot express. */}
      <p className="text-xs rounded-lg px-3 py-2 chip-accent">{t("profiles.urlTip")}</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <Input data-action="profiles.url.name" aria-label={t("profiles.namePlaceholder")}
          placeholder={t("profiles.namePlaceholder")}
          value={name} onChange={(e) => setName(e.target.value)} />
        <Input data-action="profiles.url.keywords" aria-label={t("profiles.keywordsPlaceholder")}
          placeholder={t("profiles.keywordsPlaceholder")}
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      </div>
      <GlobalKeywordsHint settings={settings} />
      <div className="flex flex-wrap sm:flex-nowrap gap-2">
        <Input data-action="profiles.url.url" aria-label={t("profiles.urlPlaceholder")}
          placeholder={t("profiles.urlPlaceholder")}
          value={url} onChange={(e) => setUrl(e.target.value)} />
        {url.trim() && (
          <Button data-action="profiles.url.extract" size="sm" className="whitespace-nowrap"
            title={t("profiles.extractParamsTitle")}
            onClick={extractParamsFromUrl}>
            <Extract /> {t("profiles.extractParams")}
          </Button>
        )}
      </div>
      {error && <p className="accent-bad text-xs">{error}</p>}
      <Button data-action="profiles.url.save" variant="solid" tone="accent" onClick={submitUrl}
        disabled={saving || !url}>
        {saving
          ? t("common.saving")
          : t(editingId !== null ? "profiles.saveChanges" : "profiles.saveProfile")}
      </Button>
    </div>
  );
}
