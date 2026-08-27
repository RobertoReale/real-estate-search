/** The monitored-searches panel: the mode switcher, the list, and the dialogs.
 *
 * All of the behaviour lives in `useSearchProfiles`; everything below is
 * composition. The five modes are mutually exclusive views over that one state
 * machine, which is why each panel takes the whole `sp` object rather than a
 * hand-picked slice — they are not independently reusable widgets, and pretending
 * otherwise would mean threading twenty props through each of them.
 */

import { useSearchProfiles } from "../hooks/useSearchProfiles";
import type { SearchProfile, Settings } from "../types";
import { AssistantPanel } from "./searchProfiles/AssistantPanel";
import { BuilderForm } from "./searchProfiles/BuilderForm";
import { BulkToolbar } from "./searchProfiles/BulkToolbar";
import { DeleteDialog } from "./searchProfiles/DeleteDialog";
import { MultiPanel } from "./searchProfiles/MultiPanel";
import { ProfileList } from "./searchProfiles/ProfileList";
import { UrlForm } from "./searchProfiles/UrlForm";

interface Props {
  profiles: SearchProfile[];
  settings: Settings | null;
  onChanged: () => void;
}

export default function SearchProfiles({ profiles, settings, onChanged }: Props) {
  const sp = useSearchProfiles({ profiles, settings, onChanged });
  const { t, mode, setMode, resetForm } = sp;

  return (
    <section className="glass rounded-2xl p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold text-base">
          {t("profiles.title")}{" "}
          <span className="t-muted text-sm">({profiles.length})</span>
        </h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "assistant") setMode("assistant"); }}>
            {mode === "assistant" ? t("common.cancel") : t("profiles.modeAssistant")}
          </button>
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "builder") setMode("builder"); }}>
            {mode === "builder" ? t("common.cancel") : t("profiles.modeBuilder")}
          </button>
          <button className="btn-ghost"
            onClick={() => { resetForm(); if (mode !== "url") setMode("url"); }}>
            {mode === "url" ? t("common.cancel") : t("profiles.modeUrl")}
          </button>
        </div>
      </div>

      {mode === "assistant" && <AssistantPanel sp={sp} />}
      {mode === "multi" && <MultiPanel sp={sp} />}
      {mode === "url" && <UrlForm sp={sp} />}
      {mode === "builder" && <BuilderForm sp={sp} />}

      {profiles.length === 0 && mode === "closed" && (
        <p className="text-sm t-muted">{t("profiles.empty")}</p>
      )}

      {profiles.length > 1 && <BulkToolbar sp={sp} />}

      <ProfileList sp={sp} />

      <DeleteDialog sp={sp} />
    </section>
  );
}
