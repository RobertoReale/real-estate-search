/** The third step: start the first scan, and give it something to watch.
 *
 *  A first scan is minutes long and most of that is spent deliberately idle
 *  between page requests, which is exactly the shape of wait a user reads as a
 *  hang. So this is the one place in the app that spends the scan's live
 *  progress on the screen rather than on one truncated line in the header: what
 *  it is doing, which search of how many, and how much it has collected.
 *
 *  **A count, never a proportion.** `ScanProgressOut` declares totals only when
 *  a portal has stated one, and a bar that fills to 90% and stops teaches the
 *  user the app lies. Every number here rises and none of them is a fraction of
 *  anything, which is also why the sentence about the pauses is on the screen —
 *  a wait that has been explained is not the same wait.
 */
import { useNavigate } from "react-router-dom";

import { useT, type TranslationKey } from "../../i18n";
import { useScanStatus, useTriggerScan } from "../../queries/dashboard";
import { useToasts } from "../../components/Toast";
import { Button } from "../../ui";
import { Cog, Note, Run } from "../../ui/icons";
import { SETUP } from "../params";

/** The scanner's phases, as something a person reads. Anything unrecognised
 *  falls back to "scanning" rather than to the backend's English `detail`:
 *  a new phase name reaching an old dashboard should be vague, not untranslated. */
const PHASE_LABEL: Record<string, TranslationKey> = {
  starting: "onboarding.phaseStarting",
  locating: "onboarding.phaseLocating",
  fetching: "onboarding.phaseFetching",
  waiting: "onboarding.phaseWaiting",
  saving: "onboarding.phaseSaving",
};

export default function FirstScan() {
  const t = useT();
  const toasts = useToasts();
  const navigate = useNavigate();
  const status = useScanStatus().data ?? null;
  const triggerScan = useTriggerScan();

  const running = status?.running ?? false;
  const progress = status?.progress ?? null;
  const phaseKey = progress?.phase ? PHASE_LABEL[progress.phase] : undefined;

  function scanNow() {
    triggerScan.mutate(undefined, {
      onError: (e) => toasts.fail(e, { doing: t("toast.scanFailed"), retry: scanNow }),
    });
  }

  return (
    <div className="space-y-4">
      <p className="text-sm t-muted">{t("onboarding.scanBody")}</p>

      <Button data-action="onboarding.scan" variant="solid" tone="accent"
        onClick={scanNow} disabled={running}>
        <Run /> {running ? t("onboarding.scanRunning") : t("onboarding.scanStart")}
      </Button>

      {/* One live region for the whole step: a scan that moves from "reading
          page 2" to "pausing" to "saving" is one status changing, and three
          separate `role="status"` elements would announce it three times. */}
      <div role="status" className="space-y-1 text-sm">
        {running ? (
          <>
            <p className="t-strong">
              {phaseKey
                ? t(phaseKey, { page: progress?.page ?? 0 })
                : t("onboarding.scanRunning")}
            </p>
            {progress && progress.profile_total > 0 && (
              <p className="t-muted">
                {t("onboarding.scanSearchOf", {
                  index: progress.profile_index, total: progress.profile_total,
                })}
              </p>
            )}
            <p className="t-muted">
              {t("onboarding.scanFound", { count: progress?.listings ?? 0 })}
            </p>
          </>
        ) : (
          <p className="t-muted">{t("onboarding.scanIdle")}</p>
        )}
      </div>

      <p className="flex items-start gap-2 text-xs leading-relaxed t-muted">
        <Note className="mt-0.5 shrink-0" />
        {t("onboarding.scanPatience")}
      </p>
      {/* The step used to end here with a sentence telling the user to open
          Settings afterwards and find the Telegram fields — instructions about
          controls on another screen, which is the thing this guide exists to
          stop doing. The control is the sentence now. */}
      <div className="space-y-2 border-t border-line pt-4">
        <p className="text-sm t-muted">{t("onboarding.setupBody")}</p>
        <Button data-action="onboarding.setup" onClick={() => void navigate(SETUP)}>
          <Cog /> {t("onboarding.setupOpen")}
        </Button>
      </div>
    </div>
  );
}
