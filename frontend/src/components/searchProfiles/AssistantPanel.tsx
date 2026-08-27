/** Mode "assistant": the plain-language box. A query with alternatives
 * ("o"/"oppure") hands off to MultiPanel; a single one opens the builder. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { ASSISTANT_EXAMPLES } from "./constants";

export function AssistantPanel({ sp }: { sp: SearchProfilesState }) {
  const { t, query, setQuery, ask, asking, error } = sp;
  return (
    <div className="mb-4 p-4 rounded-xl panel space-y-3">
      <p className="text-xs t-muted">{t("profiles.assistantIntro")}</p>
      <div className="flex flex-wrap gap-2">
        <input
          className="input flex-1 basis-full sm:basis-auto sm:min-w-[18rem]"
          placeholder={t("profiles.assistantPlaceholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          autoFocus />
        <button className="btn-primary" onClick={ask}
          disabled={asking || !query.trim()}>
          {asking ? t("profiles.assistantReading") : t("profiles.assistantSubmit")}
        </button>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs t-dim">{t("profiles.assistantTry")}</span>
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
  );
}
