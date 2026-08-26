import { useT } from "../../i18n";
import type { Settings } from "../../types";
import { Link, SecretStatus, SectionHeading } from "./controls";
import { useSectionState, type Section } from "./state";

interface Values {
  backend: string;
  baseUrl: string;
  apiKey: string;
  model: string;
}

export function useAssistantSection(): Section<Values> {
  return useSectionState<Values>(
    { backend: "deterministic", baseUrl: "", apiKey: "", model: "" },
    (s) => ({
      backend: s.nl_parser_backend || "deterministic",
      baseUrl: s.llm_base_url || "",
      apiKey: "", // write-only
      model: s.llm_model || "",
    }),
    (v) => {
      const p: Partial<Settings> = {
        nl_parser_backend: v.backend,
        llm_base_url: v.baseUrl,
        llm_model: v.model,
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

  return (
    <>
      <SectionHeading>{t("settings.assistantTitle")}</SectionHeading>
      <p className="text-xs t-dim mb-2">{t("settings.assistantNote")}</p>
      <select className="input w-full" value={values.backend}
        onChange={(e) => set("backend", e.target.value)}>
        <option value="deterministic">{t("settings.backendBuiltin")}</option>
        <option value="llm">{t("settings.backendLlm")}</option>
      </select>
      {values.backend === "llm" && (
        <div className="space-y-2 mt-2">
          <p className="text-xs t-dim">
            {t("settings.llmHintA")}
            <Link href="https://ollama.com">Ollama</Link>
            {t("settings.llmHintB")}
            <code className="px-1 rounded bg-black/10 dark:bg-white/10 select-all">http://localhost:11434/v1</code>
            {t("settings.llmHintC")}
            <code className="px-1 rounded bg-black/10 dark:bg-white/10">llama3.1</code>
            {t("settings.llmHintD")}
          </p>
          <input className="input w-full" placeholder={t("settings.llmBaseUrl")}
            value={values.baseUrl} onChange={(e) => set("baseUrl", e.target.value)} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input className="input w-full" placeholder={t("settings.llmModel")}
              value={values.model} onChange={(e) => set("model", e.target.value)} />
            <div>
              <input className="input w-full" type="password"
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
