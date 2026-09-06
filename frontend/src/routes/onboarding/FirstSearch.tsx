/** The second step: the three ways of creating a search, offered as one choice.
 *
 *  Nothing here is a new way of making a search. The assistant, the form and
 *  the URL paste are the same three panels the Searches screen renders, driven
 *  by the same `useSearchProfiles` state machine — a fourth implementation of
 *  "save a search" is how two screens end up disagreeing about what a valid one
 *  is. What this file adds is the framing that screen cannot give them: on
 *  Searches the three are a row of mode buttons above a list, which reads as
 *  three features, and a first-time user has to guess which of them is *the*
 *  one. Here they are three answers to a question that has already been asked,
 *  each with the one line that says who it suits, and picking one replaces the
 *  choice rather than adding a panel under it.
 *
 *  The URL way carries the tip about portal filters, and only the URL way: it
 *  is advice about a control the user is looking at, and on the old screen it
 *  was printed next to two other ways it does not apply to.
 */
import { useSearchProfiles } from "../../hooks/useSearchProfiles";
import { AssistantPanel } from "../../components/searchProfiles/AssistantPanel";
import { BuilderForm } from "../../components/searchProfiles/BuilderForm";
import { MultiPanel } from "../../components/searchProfiles/MultiPanel";
import { UrlForm } from "../../components/searchProfiles/UrlForm";
import { useT, type TranslationKey } from "../../i18n";
import { useRefreshDashboard } from "../../queries/properties";
import type { SearchProfile, Settings } from "../../types";
import { Button, cx, FOCUS_RING } from "../../ui";
import { BuildSearch, Describe, PasteUrl } from "../../ui/icons";

type Way = "assistant" | "builder" | "url";

const WAYS: {
  way: Way;
  action: string;
  Glyph: typeof Describe;
  title: TranslationKey;
  body: TranslationKey;
}[] = [
  {
    way: "assistant", action: "onboarding.wayAssistant", Glyph: Describe,
    title: "onboarding.wayAssistant", body: "onboarding.wayAssistantBody",
  },
  {
    way: "builder", action: "onboarding.wayBuilder", Glyph: BuildSearch,
    title: "onboarding.wayBuilder", body: "onboarding.wayBuilderBody",
  },
  {
    way: "url", action: "onboarding.wayUrl", Glyph: PasteUrl,
    title: "onboarding.wayUrl", body: "onboarding.wayUrlBody",
  },
];

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  /** Called once a search has actually been saved, so the guide can open the
   *  step that only means anything after that. */
  onCreated: () => void;
}

export default function FirstSearch({ profiles, settings, onCreated }: Props) {
  const t = useT();
  const refresh = useRefreshDashboard();
  const sp = useSearchProfiles({
    profiles, settings,
    onChanged: () => { refresh(); onCreated(); },
  });
  const { mode, setMode, resetForm } = sp;

  return (
    <div className="space-y-4">
      <p className="text-sm t-muted">{t("onboarding.searchBody")}</p>

      {mode === "closed" ? (
        <ul className="grid gap-3 sm:grid-cols-3">
          {WAYS.map(({ way, action, Glyph, title, body }) => (
            <li key={way}>
              <button type="button" data-action={action}
                onClick={() => { resetForm(); setMode(way); }}
                className={cx(
                  "h-full w-full rounded-card border border-line p-4 text-left",
                  "hover:border-line-strong", FOCUS_RING,
                )}>
                <span className="flex items-center gap-2 font-medium text-sm t-strong">
                  <Glyph className="shrink-0" /> {t(title)}
                </span>
                <span className="mt-1.5 block text-xs leading-relaxed t-muted">
                  {t(body)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="space-y-3">
          <Button data-action="onboarding.wayBack" size="sm" onClick={resetForm}>
            {t("onboarding.wayBack")}
          </Button>

          {mode === "assistant" && <AssistantPanel sp={sp} />}
          {mode === "multi" && <MultiPanel sp={sp} />}
          {mode === "builder" && <BuilderForm sp={sp} />}
          {mode === "url" && (
            <>
              <UrlForm sp={sp} />
              <p className="text-xs leading-relaxed t-muted">
                <strong className="t-strong">{t("onboarding.urlTip")}</strong>{" "}
                {t("onboarding.urlTipBody")}
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
