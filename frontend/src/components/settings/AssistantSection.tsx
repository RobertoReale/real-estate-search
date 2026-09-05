import { useT } from "../../i18n";
import type { Settings } from "../../types";
import { Link, SecretStatus, SectionHeading } from "./controls";
import { useSectionState, type Section } from "./state";

interface Values {
  backend: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  audit: boolean;
}

export function useAssistantSection(): Section<Values> {
  return useSectionState<Values>(
    { backend: "deterministic", baseUrl: "", apiKey: "", model: "", audit: false },
    (s) => ({
      backend: s.nl_parser_backend || "deterministic",
      baseUrl: s.llm_base_url || "",
      apiKey: "", // write-only
      model: s.llm_model || "",
      audit: s.listing_audit_enabled ?? false,
    }),
    (v) => {
      const p: Partial<Settings> = {
        nl_parser_backend: v.backend,
        llm_base_url: v.baseUrl,
        llm_model: v.model,
        listing_audit_enabled: v.audit,
      };
      if (v.apiKey.trim()) p.llm_api_key = v.apiKey.trim();
      return p;
    },
  );
}

export function AssistantSection(
  { section, settings }: { section: Section<Values>; settings: Settings },
) {
  const t = useT();
  const { values, set } = section;
  // One endpoint, two optional readers: the assistant backend and the listing
  // auditor. Whichever is on, the connection fields below are what it uses —
  // so they are shown for either, never duplicated per feature.
  const needsLlm = values.backend === "llm" || values.audit;

  return (
    <>
      <SectionHeading>{t("settings.assistantTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.assistantNote")}</p>
      <select data-action="settings.assistant.backend" className="input w-full" value={values.backend}
        aria-label={t("settings.assistantTitle")}
        onChange={(e) => set("backend", e.target.value)}>
        <option value="deterministic">{t("settings.backendBuiltin")}</option>
        <option value="llm">{t("settings.backendLlm")}</option>
      </select>

      <SectionHeading>{t("settings.auditTitle")}</SectionHeading>
      <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
        <input data-action="settings.assistant.audit" type="checkbox" checked={values.audit}
          onChange={(e) => set("audit", e.target.checked)} />
        {t("settings.auditEnable")}
      </label>
      <p className="text-xs t-dim mt-1">{t("settings.auditNote")}</p>

      {needsLlm && (
        <div className="space-y-2 mt-2">
          <p className="text-xs t-dim">
            {t("settings.llmHintA")}
            <Link href="https://ollama.com">Ollama</Link>
            {t("settings.llmHintB")}
            <code className="px-1 rounded bg-wash select-all">http://localhost:11434/v1</code>
            {t("settings.llmHintC")}
            <code className="px-1 rounded bg-wash">llama3.1</code>
            {t("settings.llmHintD")}
          </p>
          <input data-action="settings.assistant.baseUrl" className="input w-full" placeholder={t("settings.llmBaseUrl")}
            value={values.baseUrl} onChange={(e) => set("baseUrl", e.target.value)} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input data-action="settings.assistant.model" className="input w-full" placeholder={t("settings.llmModel")}
              value={values.model} onChange={(e) => set("model", e.target.value)} />
            <div>
              <input data-action="settings.assistant.apiKey" className="input w-full" type="password"
                placeholder={t(settings.llm_api_key_set ? "settings.llmKeySaved" : "settings.llmKeyPlaceholder")}
                value={values.apiKey} onChange={(e) => set("apiKey", e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.llm_api_key_set} dirty={!!values.apiKey.trim()} />
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
