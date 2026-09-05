/** Mode "builder": the guided form.
 *
 * The filter set is deliberately small: every token in it is measured against
 * both portals' own result totals, and a guessed one 404s silently (see
 * docs/architecture.md on portal filter tokens). Anything finer is the "paste a URL" path,
 * which the form links to from right beside the filters. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { PortalBadge } from "../PortalBadge";
import type { SearchBuilderParams } from "../../types";
import { CONDITIONS, FEATURES, FLOORS, UNSUPPORTED_LABELS } from "./constants";
import { GlobalKeywordsHint } from "./helpers";
import { Button, Checkbox, Chip, Field, Input } from "../../ui";
import { External, Hint, Warning } from "../../ui/icons";

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
              <Chip key={part} tone="positive" size="md">{part}</Chip>
            ))}
            <button data-action="profiles.builder.reword" className="text-xs accent-link ml-auto"
              onClick={() => setMode("assistant")}>
              {t("profiles.reword")}
            </button>
          </div>
          {/* assumptions the parser had to make: visible, not buried */}
          {assistant.notes.map((note) => (
            <p key={note} className="flex items-start gap-1.5 text-xs t-muted">
              <Hint className="shrink-0 mt-0.5" /> {note}
            </p>
          ))}
          {assistant.warnings.map((warning) => (
            <p key={warning}
              className="flex items-start gap-1.5 text-xs text-caution-ink">
              <Warning className="shrink-0 mt-0.5" /> {warning}
            </p>
          ))}
          <p className="text-xs t-dim">{t("profiles.checkFields")}</p>
        </div>
      ) : (
        <p className="text-xs t-muted">
          {t("profiles.builderIntroPrefix")}
          <button data-action="profiles.builder.toUrlIntro" className="accent-link underline"
            onClick={() => setMode("url")}>{t("profiles.modeUrl")}</button>
          {t("profiles.builderIntroSuffix")}
        </p>
      )}
      {/* two columns on a phone, one flowing row from `sm` up — the
          `col-span-2` below is inert once the container turns into a flex */}
      <div className="grid grid-cols-2 gap-3 items-end sm:flex sm:flex-wrap">
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="builder-contract">{t("common.contract")}</label>
          <select data-action="profiles.builder.contract" id="builder-contract" className="input w-full sm:w-28" value={params.contract}
            onChange={(e) => setParam({ contract: e.target.value as "sale" | "rent" })}>
            <option value="sale">{t("filters.buy")}</option>
            <option value="rent">{t("filters.rent")}</option>
          </select>
        </div>
        <Field label={t("profiles.cityRequired")}>
          <Input data-action="profiles.builder.city" className="sm:w-40" placeholder={t("filters.cityPlaceholder")}
            value={params.city} onChange={(e) => setParam({ city: e.target.value })} />
        </Field>
        <Field label={<span title={t("profiles.provinceTitle")}>{t("profiles.province")}</span>}>
          <Input data-action="profiles.builder.province" className="sm:w-32" placeholder={t("profiles.optional")}
            value={params.province} onChange={(e) => setParam({ province: e.target.value })} />
        </Field>
        <Field label={<span title={t("profiles.zoneTitle")}>{t("filters.zone")}</span>}>
          <Input data-action="profiles.builder.zone" className="sm:w-32" placeholder={t("profiles.optional")}
            value={params.zone} onChange={(e) => setParam({ zone: e.target.value })} />
        </Field>
        <Field label={t("filters.minPrice")}>
          <Input data-action="profiles.builder.minPrice" className="sm:w-24" type="number" value={params.min_price}
            onChange={(e) => setParam({ min_price: e.target.value })} />
        </Field>
        <Field label={t("filters.maxPrice")}>
          <Input data-action="profiles.builder.maxPrice" className="sm:w-24" type="number" value={params.max_price}
            onChange={(e) => setParam({ max_price: e.target.value })} />
        </Field>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="builder-min-rooms">{t("profiles.minRooms")}</label>
          <select data-action="profiles.builder.minRooms" id="builder-min-rooms" className="input w-full sm:w-24" value={params.min_rooms}
            onChange={(e) => setParam({ min_rooms: e.target.value })}>
            <option value="">{t("common.any")}</option>
            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}+</option>)}
          </select>
        </div>
        <Field label={t("filters.minSqm")}>
          <Input data-action="profiles.builder.minSqm" className="sm:w-20" type="number" value={params.min_sqm}
            onChange={(e) => setParam({ min_sqm: e.target.value })} />
        </Field>
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
          <label className="text-xs t-muted" htmlFor="builder-floor">{t("filters.floor")}</label>
          <select data-action="profiles.builder.floor" id="builder-floor" className="input w-full sm:w-36" value={params.floor}
            onChange={(e) => setParam({
              floor: e.target.value as SearchBuilderParams["floor"],
            })}>
            {FLOORS.map(([v, label]) => <option key={v} value={v}>{t(label)}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs t-muted" htmlFor="builder-condition">{t("profiles.condition")}</label>
          <select data-action="profiles.builder.condition" id="builder-condition" className="input w-full sm:w-44" value={params.condition}
            onChange={(e) => setParam({
              condition: e.target.value as SearchBuilderParams["condition"],
            })}>
            {CONDITIONS.map(([v, label]) => <option key={v} value={v}>{t(label)}</option>)}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2">
        {FEATURES.map(([key, label]) => (
          <Checkbox key={key} data-action="profiles.builder.feature" className="min-h-11 sm:min-h-0"
            label={t(label)} checked={params[key]}
            onCheckedChange={(v) => setParam({ [key]: v === true })} />
        ))}
      </div>

      {/* The full-power escape hatch, kept next to the filters so it is
          found exactly when the user reaches for a filter that isn't here. */}
      <p className="text-xs rounded-lg px-3 py-2 chip-accent">
        {t("profiles.builderTipPrefix")}
        <button data-action="profiles.builder.toUrlTip" className="underline font-medium"
          onClick={() => setMode("url")}>{t("profiles.builderTipLink")}</button>
        {t("profiles.builderTipSuffix")}
      </p>

      <div className="grid sm:grid-cols-2 gap-3">
        <Input data-action="profiles.builder.name" aria-label={t("profiles.profileNamePlaceholder")}
          placeholder={t("profiles.profileNamePlaceholder")}
          value={name} onChange={(e) => setName(e.target.value)} />
        <Input data-action="profiles.builder.keywords" aria-label={t("profiles.keywordsPlaceholder")}
          placeholder={t("profiles.keywordsPlaceholder")}
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />
      </div>
      <GlobalKeywordsHint settings={settings} />

      {!built && (
        <Button data-action="profiles.builder.generate" variant="solid" tone="accent" onClick={generate}
          disabled={generating || !params.city.trim()}>
          {generating ? t("profiles.generating") : t("profiles.generate")}
        </Button>
      )}

      {built && (
        <div className="space-y-2 pt-1">
          <p className="text-xs t-muted">{t("profiles.checkGenerated")}</p>
          {(["immobiliare", "idealista"] as const).map((portal) => (
            <label key={portal}
              className="flex items-center gap-3 p-2.5 rounded-xl panel cursor-pointer">
              <input data-action="profiles.builder.usePortal" type="checkbox" checked={usePortals[portal]}
                onChange={(e) =>
                  setUsePortals((u) => ({ ...u, [portal]: e.target.checked }))} />
              <PortalBadge portal={portal} />
              <span className="text-xs t-muted truncate flex-1">{built[portal]}</span>
              <a data-action="profiles.builder.openBuilt" href={built[portal]} target="_blank" rel="noreferrer"
                className="accent-link text-xs shrink-0"
                onClick={(e) => e.stopPropagation()}>
                {t("common.open")} <External />
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
          <Button data-action="profiles.builder.create" variant="solid" tone="accent"
            onClick={createFromBuilder}
            disabled={saving || (!usePortals.immobiliare && !usePortals.idealista)}>
            {saving
              ? t("common.saving")
              : t(editingId !== null ? "profiles.saveChanges" : "profiles.createProfilesButton")}
          </Button>
        </div>
      )}
      {!built && error && <p className="accent-bad text-xs">{error}</p>}
    </div>
  );
}
