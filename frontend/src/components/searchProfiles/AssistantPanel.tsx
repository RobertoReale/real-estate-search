/** Mode "assistant": the plain-language box. A query with alternatives
 * ("o"/"oppure") hands off to MultiPanel; a single one opens the builder. */

import type { SearchProfilesState } from "../../hooks/useSearchProfiles";
import { ASSISTANT_EXAMPLES } from "./constants";
import { Button, Input } from "../../ui";

export function AssistantPanel({ sp }: { sp: SearchProfilesState }) {
  const { t, query, setQuery, ask, asking, error } = sp;
  return (
    <div className="mb-4 p-4 rounded-xl panel space-y-3">
      <p className="text-xs t-muted">{t("profiles.assistantIntro")}</p>
      <div className="flex flex-wrap gap-2">
        <Input data-action="profiles.assistant.query"
          className="flex-1 basis-full sm:basis-auto sm:min-w-[18rem]"
          aria-label={t("profiles.assistantPlaceholder")}
          placeholder={t("profiles.assistantPlaceholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          autoFocus />
        <Button data-action="profiles.assistant.ask" variant="solid" tone="accent" onClick={ask}
          disabled={asking || !query.trim()}>
          {asking ? t("profiles.assistantReading") : t("profiles.assistantSubmit")}
        </Button>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs t-dim">{t("profiles.assistantTry")}</span>
        {ASSISTANT_EXAMPLES.map((example) => (
          <Button data-action="profiles.assistant.example" key={example}
            variant="ghost" tone="accent" size="sm"
            onClick={() => setQuery(example)}>
            {example}
          </Button>
        ))}
      </div>
      {error && <p className="accent-bad text-xs">{error}</p>}
    </div>
  );
}
