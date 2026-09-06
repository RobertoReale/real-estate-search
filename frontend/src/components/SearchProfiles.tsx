/** The monitored-searches panel: the mode switcher, the list, and the dialogs.
 *
 * All of the behaviour lives in `useSearchProfiles`; everything below is
 * composition. The five modes are mutually exclusive views over that one state
 * machine, which is why each panel takes the whole `sp` object rather than a
 * hand-picked slice — they are not independently reusable widgets, and pretending
 * otherwise would mean threading twenty props through each of them.
 */

import { useSearchProfiles } from "../hooks/useSearchProfiles";
import type { SearchBuilderParams, SearchProfile, Settings } from "../types";
import { AssistantPanel } from "./searchProfiles/AssistantPanel";
import { BuilderForm } from "./searchProfiles/BuilderForm";
import { BulkToolbar } from "./searchProfiles/BulkToolbar";
import { DeleteDialog } from "./searchProfiles/DeleteDialog";
import { MultiPanel } from "./searchProfiles/MultiPanel";
import { ProfileList } from "./searchProfiles/ProfileList";
import { UrlForm } from "./searchProfiles/UrlForm";
import { Button, Card, EmptyState } from "../ui";
import { BuildSearch, Describe, ICON_SIZE, PasteUrl, Searches } from "../ui/icons";

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void;
  /** A builder to open on, when the page was reached from the grid's filters. */
  prefill?: SearchBuilderParams | null;
}

export default function SearchProfiles({ profiles, settings, onChanged, prefill }: Props) {
  const sp = useSearchProfiles({ profiles, settings, onChanged, prefill });
  const { t, mode, setMode, resetForm } = sp;

  // Whether a channel is configured is a fact about the account rather than
  // about a search, so it is not stated in here at all: `routes/searches/`
  // renders one banner for the page, above this list. The select in each row
  // still says which channels are off — that one is about the choice being
  // made, and it is the only place the distinction belongs.

  return (
    <Card asChild padding="lg">
      <section>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="flex items-center gap-1.5 font-semibold text-base">
            <Searches className="shrink-0" />
            {t("profiles.title")}{" "}
            <span className="t-muted text-sm">({profiles.length})</span>
          </h2>
          <div className="flex flex-wrap gap-2">
            <Button data-action="profiles.mode.assistant"
              onClick={() => { resetForm(); if (mode !== "assistant") setMode("assistant"); }}>
              {mode === "assistant"
                ? t("common.cancel")
                : <><Describe /> {t("profiles.modeAssistant")}</>}
            </Button>
            <Button data-action="profiles.mode.builder"
              onClick={() => { resetForm(); if (mode !== "builder") setMode("builder"); }}>
              {mode === "builder"
                ? t("common.cancel")
                : <><BuildSearch /> {t("profiles.modeBuilder")}</>}
            </Button>
            <Button data-action="profiles.mode.url"
              onClick={() => { resetForm(); if (mode !== "url") setMode("url"); }}>
              {mode === "url"
                ? t("common.cancel")
                : <><PasteUrl /> {t("profiles.modeUrl")}</>}
            </Button>
          </div>
        </div>

        {mode === "assistant" && <AssistantPanel sp={sp} />}
        {mode === "multi" && <MultiPanel sp={sp} />}
        {mode === "url" && <UrlForm sp={sp} />}
        {mode === "builder" && <BuilderForm sp={sp} />}

        {/* The list is the body of this panel, so with no searches the panel is
            a heading over nothing. Stated at the size of the thing that is
            missing, and pointing at the three buttons above it rather than
            adding a fourth that says the same. */}
        {profiles.length === 0 && mode === "closed" && (
          <EmptyState
            icon={<Searches size={ICON_SIZE.display} strokeWidth={1.25} />}
            title={t("profiles.emptyTitle")}
            description={t("profiles.empty")} />
        )}

        {profiles.length > 1 && <BulkToolbar sp={sp} />}

        <ProfileList sp={sp} />

        <DeleteDialog sp={sp} />
      </section>
    </Card>
  );
}
