/** Mode "builder": the guided form.
 *
 * The filter set is deliberately small: every token in it is measured against
 * both portals' own result totals, and a guessed one 404s silently (see
 * CLAUDE.md on portal filter tokens). Anything finer is the "paste a URL" path,
 * which the form links to from right beside the filters. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { PortalBadge } from "../PortalBadge";
import type { SearchBuilderParams } from "../../types";
import { CONDITIONS, FEATURES, FLOORS, UNSUPPORTED_LABELS } from "./constants";
import { GlobalKeywordsHint } from "./helpers";

export function BuilderForm({ sp }: { sp: SearchProfilesState }) {
  const { t, settings, assistant, setMode, params, setParam, name, setName, keywords, setKeywords,
    built, generate, generating, createFromBuilder, saving, editingId, usePortals, setUsePortals, error } = sp;
  return (
    <div className="mb-4 p-4 rounded-xl panel space-y-3">
      {assistant ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs t-muted">{t("profiles.understood")}</span>
            {assistant.interpretation.map((part) => (
              <span key={part}
                className="text-xs chip-emerald px-2 py-1 rounded-lg font-medium">
                {part}
              </span>
            ))}
            <button className="text-xs accent-link ml-auto"
              onClick={() => setMode("assistant")}>
              {t("profiles.reword")}
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
          <p className="text-xs t-dim">{t("profiles.checkFields")}</p>
        </div>
      ) : (
        <p className="text-xs t-muted">
          {t("profiles.builderIntroPrefix")}
          <button className="accent-link underline"
            onClick={() => setMode("url")}>{t("profiles.modeUrl")}</button>
          {t("profiles.builderIntroSuffix")}
        </p>
      )}
      {/* two columns on a phone, one flowing row from `sm` up — the
          `col-span-2` below is inert once the container turns into a flex */}
      <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("common.contract")}</label>
          <select className="input w-full sm:w-28" value={params.contract}
            onChange={(e) => setParam({ contract: e.target.value as "sale" | "rent" })}>
            <option value="sale">{t("filters.buy")}</option>
            <option value="rent">{t("filters.rent")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("profiles.cityRequired")}</label>
          <input className="input w-full sm:w-40" placeholder={t("filters.cityPlaceholder")}
            value={params.city} onChange={(e) => setParam({ city: e.target.value })} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" title={t("profiles.provinceTitle")}>
            {t("profiles.province")}
          </label>
          <input className="input w-full sm:w-32" placeholder={t("profiles.optional")}
            value={params.province} onChange={(e) => setParam({ province: e.target.value })} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" title={t("profiles.zoneTitle")}>
            {t("filters.zone")}
          </label>
          <input className="input w-full sm:w-32" placeholder={t("profiles.optional")}
            value={params.zone} onChange={(e) => setParam({ zone: e.target.value })} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("filters.minPrice")}</label>
          <input className="input w-full sm:w-24" type="number" value={params.min_price}
            onChange={(e) => setParam({ min_price: e.target.value })} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("filters.maxPrice")}</label>
          <input className="input w-full sm:w-24" type="number" value={params.max_price}
            onChange={(e) => setParam({ max_price: e.target.value })} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("profiles.minRooms")}</label>
          <select className="input w-full sm:w-24" value={params.min_rooms}
            onChange={(e) => setParam({ min_rooms: e.target.value })}>
            <option value="">{t("common.any")}</option>
            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}+</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("filters.minSqm")}</label>
          <input className="input w-full sm:w-20" type="number" value={params.min_sqm}
            onChange={(e) => setParam({ min_sqm: e.target.value })} />
        </div>
      </div>
      {/* Everything below is applied to BOTH portals. It is deliberately a
          small, verified set: each token is measured on both Immobiliare
          and Idealista (a guessed one 404s silently). For anything finer,
          the "Paste a URL" note at the end is the full-power path. */}
      <p className="text-xs font-medium t-muted -mb-1">
        {t("profiles.moreCriteria")}{" "}
        <span className="font-normal t-dim">{t("profiles.moreCriteriaHint")}</span>
      </p>
      <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("filters.floor")}</label>
          <select className="input w-full sm:w-36" value={params.floor}
            onChange={(e) => setParam({
              floor: e.target.value as SearchBuilderParams["floor"],
            })}>
            {FLOORS.map(([v, label]) => <option key={v} value={v}>{t(label)}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted">{t("profiles.condition")}</label>
          <select className="input w-full sm:w-44" value={params.condition}
            onChange={(e) => setParam({
              condition: e.target.value as SearchBuilderParams["condition"],
            })}>
            {CONDITIONS.map(([v, label]) => <option key={v} value={v}>{t(label)}</option>)}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {FEATURES.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm min-h-11 sm:min-h-0">
            <input type="checkbox" checked={params[key]}
              onChange={(e) => setParam({ [key]: e.target.checked })} />
            {t(label)}
          </label>
        ))}
      </div>

      {/* The full-power escape hatch, kept next to the filters so it is
          found exactly when the user reaches for a filter that isn't here. */}
      <p className="text-xs rounded-lg px-3 py-2 chip-blue">
        {t("profiles.builderTipPrefix")}
        <button className="underline font-medium"
          onClick={() => setMode("url")}>{t("profiles.builderTipLink")}</button>
        {t("profiles.builderTipSuffix")}
      </p>

      <div className="grid sm:grid-cols-2 gap-3">
        <input className="input w-full" placeholder={t("profiles.profileNamePlaceholder")}
          value={name} onChange={(e) => setName(e.target.value)} />
        <input className="input w-full" placeholder={t("profiles.keywordsPlaceholder")}
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      </div>
      <GlobalKeywordsHint settings={settings} />

      {!built && (
        <button className="btn-primary" onClick={generate}
          disabled={generating || !params.city.trim()}>
          {generating ? t("profiles.generating") : t("profiles.generate")}
        </button>
      )}

      {built && (
        <div className="space-y-2 pt-1">
          <p className="text-xs t-muted">{t("profiles.checkGenerated")}</p>
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
                {t("modal.open")}
              </a>
            </label>
          ))}
          {params.zone.trim() && usePortals.idealista && (
            <p className="text-xs t-muted">
              {t(built.idealista_zone_page ? "profiles.zoneKnown" : "profiles.zoneUnknown", {
                zone: params.zone.trim(),
              })}
            </p>
          )}
          {usePortals.idealista && built.idealista_unsupported?.length ? (
            <p className="text-xs t-muted">
              {t("profiles.idealistaUnsupported", {
                filters: built.idealista_unsupported
                  .map((k) => (UNSUPPORTED_LABELS[k] ? t(UNSUPPORTED_LABELS[k]) : k))
                  .join(", "),
              })}
            </p>
          ) : null}
          {error && <p className="accent-bad text-xs">{error}</p>}
          <button className="btn-primary" onClick={createFromBuilder}
            disabled={saving || (!usePortals.immobiliare && !usePortals.idealista)}>
            {saving
              ? t("common.saving")
              : t(editingId !== null ? "profiles.saveChanges" : "profiles.createProfilesButton")}
          </button>
        </div>
      )}
      {!built && error && <p className="accent-bad text-xs">{error}</p>}
    </div>
  );
}
