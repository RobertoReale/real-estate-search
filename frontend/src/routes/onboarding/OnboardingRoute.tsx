/** The guided first run: what the app is, the first search, the first scan.
 *
 *  A fresh database has to reach a working search without the user reading
 *  anything outside the app, and until now the whole of that was a three-item
 *  numbered list on the empty listings screen — instructions describing
 *  controls on a *different* screen, which is documentation with extra steps.
 *  This is the same three things, in the order they have to happen, with the
 *  actual control for each one in front of the sentence that asks for it.
 *
 *  It is a destination rather than a modal, and that is deliberate: a wizard
 *  over the top of the app cannot be left half-finished and come back to, and
 *  the second of these steps is one a user may legitimately spend ten minutes
 *  on. Being a route means the navigation stays reachable, the address can be
 *  returned to, and "skip" is a decision the app remembers rather than a dialog
 *  that reopens.
 *
 *  Which step is on screen is `steps.ts`, not this file — the clamp that keeps
 *  the scan step out of reach until there is something to scan is a rule, and a
 *  rule tested directly does not have to be re-derived from a render.
 */
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import FirstScan from "./FirstScan";
import FirstSearch from "./FirstSearch";
import {
  clampStep, dismissGuide, STEPS, stepAfter, stepBefore, type Step,
} from "./steps";
import { useT, type TranslationKey } from "../../i18n";
import { useProfiles } from "../../queries/dashboard";
import { useSettings } from "../../queries/settings";
import { Button, Card, cx } from "../../ui";
import { Note, Success } from "../../ui/icons";
import { LISTINGS, withSearch } from "../params";

const STEP_NAME: Record<Step, TranslationKey> = {
  what: "onboarding.stepWhat",
  search: "onboarding.stepSearch",
  scan: "onboarding.stepScan",
};

const STEP_TITLE: Record<Step, TranslationKey> = {
  what: "onboarding.whatTitle",
  search: "onboarding.searchTitle",
  scan: "onboarding.scanTitle",
};

export default function OnboardingRoute() {
  const t = useT();
  const navigate = useNavigate();
  const { search } = useLocation();
  const profiles = useProfiles().data ?? [];
  const settings = useSettings().data ?? null;

  const [chosen, setChosen] = useState<Step>("what");
  // Set the moment a search is saved, and not read back from the query. The
  // clamp asks "is there a search yet"; between the save and the refetch
  // answering that from the server alone would bounce the user off the step the
  // save has just unlocked.
  const [created, setCreated] = useState(false);

  const hasSearch = created || profiles.length > 0;
  const step = clampStep(chosen, hasSearch);
  const previous = stepBefore(step);
  const next = clampStep(stepAfter(step), hasSearch);
  const atEnd = step === STEPS[STEPS.length - 1];

  /** Leaving, however it is done. Skipping is a decision like finishing, so it
   *  is remembered the same way — the guide does not reappear tomorrow. */
  function leave() {
    dismissGuide();
    void navigate(withSearch(LISTINGS, search));
  }

  return (
    <Card asChild padding="lg">
      <section className="max-w-3xl mx-auto space-y-5">
        <div className="space-y-1">
          <h2 className="font-semibold text-lg">{t("onboarding.title")}</h2>
          <p className="text-sm t-muted">{t("onboarding.intro")}</p>
        </div>

        {/* Where the user is, and how much is left. Not controls: a step the
            guide has not unlocked would have to explain itself, and the clamp
            already decides this without needing a disabled thing on screen. */}
        <ol className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {STEPS.map((each, index) => (
            <li key={each} aria-current={each === step ? "step" : undefined}
              className={cx("flex items-center gap-1.5",
                each === step ? "t-strong font-medium" : "t-muted")}>
              <span aria-hidden="true"
                className={cx(
                  "h-5 w-5 shrink-0 rounded-pill grid place-items-center font-bold",
                  each === step ? "bg-accent-surface text-accent-ink" : "border border-line",
                )}>
                {index + 1}
              </span>
              {t(STEP_NAME[each])}
            </li>
          ))}
        </ol>

        <div className="space-y-4">
          <h3 className="font-medium">{t(STEP_TITLE[step])}</h3>

          {step === "what" && (
            <div className="space-y-3">
              <p className="text-sm leading-relaxed">{t("onboarding.whatBody")}</p>
              <p className="flex items-start gap-2 text-xs leading-relaxed t-muted">
                <Note className="mt-0.5 shrink-0" />
                {t("onboarding.whatKeeps")}
              </p>
            </div>
          )}

          {step === "search" && (
            <FirstSearch profiles={profiles} settings={settings}
              onCreated={() => { setCreated(true); setChosen("scan"); }} />
          )}

          {step === "scan" && (
            <>
              <p className="flex items-center gap-2 text-sm accent-link">
                <Success className="shrink-0" /> {t("onboarding.searchSaved")}
              </p>
              <FirstScan />
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          {previous && (
            <Button data-action="onboarding.back" onClick={() => setChosen(previous)}>
              {t("onboarding.back")}
            </Button>
          )}
          <div className="flex-1" />
          {/* Exactly one way out at any moment: "skip" while there is still
              something ahead, "done" once there is not. Two controls that both
              mean "go to the listings" is a choice nobody can make. */}
          {atEnd ? (
            <Button data-action="onboarding.done" variant="solid" tone="accent"
              onClick={leave}>
              {t("onboarding.done")}
            </Button>
          ) : (
            <Button data-action="onboarding.skip" onClick={leave}>
              {t("onboarding.skip")}
            </Button>
          )}
          {next !== step && (
            <Button data-action="onboarding.next" variant="solid" tone="accent"
              onClick={() => setChosen(next)}>
              {t("onboarding.next")}
            </Button>
          )}
        </div>
      </section>
    </Card>
  );
}
