/** The two sweeps that repair the database, and what they answered.
 *
 *  They lived at the end of the filter bar for as long as there was a filter
 *  bar, and they never belonged there: neither of them narrows anything, and
 *  between them they took a third of the row above every visit to the grid to
 *  offer a job a user runs a handful of times a year. They are on the searches
 *  screen now — the other place in the app that is about the data rather than
 *  about looking at it, and the one a user is already on when they notice that
 *  half a search's finds have no pin.
 *
 *  What each of them is doing, whether it failed and what it answered is the
 *  mutation's own state, so there is no `finally` left that can forget to clear
 *  a flag.
 */
import { useEffect, useState } from "react";
import { useT } from "../i18n";
import {
  useCancelGeocode, useClearGeocodeCache, useGeocodeMissing, useGeocodeProgress,
} from "../queries/maintenance";
import { Button, Card, IconButton } from "../ui";
import { ClearFailed, Close, Place } from "../ui/icons";
import { ProgressBar } from "./ProgressBar";
import { useToasts } from "./Toast";

export default function MaintenanceActions() {
  const t = useT();
  const toasts = useToasts();
  const geocode = useGeocodeMissing();
  const clearCache = useClearGeocodeCache();
  const cancelGeocode = useCancelGeocode();
  const [stoppingGeocode, setStoppingGeocode] = useState(false);
  const geocoding = geocode.isPending;
  const geocodeProgress = useGeocodeProgress(geocoding);
  const geocodeResult = geocode.data ?? null;
  const cacheCleared = clearCache.data?.cleared ?? null;
  const failure = geocode.error ?? clearCache.error;

  useEffect(() => {
    if (!failure) return;
    // A backend older than these routes answers 404, and "update the backend"
    // is a far more useful thing to read than "Error 404" — and it is not a
    // refusal to act on, so it carries no advice about the request.
    if (/Error 404|Not Found/i.test(failure.message)) {
      toasts.show({ tone: "error", key: "maintenance", text: t("maintenance.backendTooOld") });
      return;
    }
    toasts.fail(failure, { key: "maintenance", doing: t("toast.geocodeFailed") });
  }, [failure, t, toasts]);

  return (
    <Card className="space-y-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold text-ink-strong">{t("maintenance.title")}</h2>
        <p className="text-xs t-muted">{t("maintenance.hint")}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button data-action="maintenance.geocode"
          className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
            geocoding
              ? "bg-sunken-strong text-ink-dim border-line-strong cursor-wait animate-pulse"
              : "bg-info-tint hover:bg-info-tint-strong text-info-ink border-info-line"
          }`}
          disabled={geocoding}
          title={t("maintenance.findCoordsTitle")}
          onClick={() => {
            // Both notices belong to one press, so the other one's answer
            // goes with it: a "2 addresses forgotten" left under a fresh
            // sweep reads as something this run just did.
            clearCache.reset();
            setStoppingGeocode(false);
            // The grid carries the coordinates, so the mutation re-reads it.
            geocode.mutate(undefined, { onSettled: () => setStoppingGeocode(false) });
          }}>
          <Place />
          {geocoding ? t("maintenance.locating") : t("maintenance.findCoords")}
        </button>
        <button data-action="maintenance.clearGeocodeCache"
          className={`px-3 py-2 text-sm font-medium rounded-lg transition border flex items-center gap-1.5 shadow-sm ${
            clearCache.isPending
              ? "bg-sunken-strong text-ink-dim border-line-strong cursor-wait animate-pulse"
              : "bg-neutral-tint hover:bg-neutral-soft text-neutral-ink border-neutral-line"
          }`}
          disabled={clearCache.isPending || geocoding}
          title={t("maintenance.retryFailedTitle")}
          onClick={() => {
            geocode.reset();
            clearCache.mutate();
          }}>
          <ClearFailed />
          {clearCache.isPending ? t("maintenance.clearing") : t("maintenance.retryFailed")}
        </button>
      </div>

      {geocoding && (
        <div className="p-3.5 rounded-xl bg-sunken border border-line animate-fade-in shadow-sm space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-accent-link flex items-center gap-1.5">
              <Place /> {t("maintenance.geocodeRunning")}
            </span>
            <Button data-action="maintenance.geocode.stop"
              size="sm" tone="negative" className="font-semibold"
              disabled={stoppingGeocode}
              onClick={() => {
                // Held until the sweep itself ends rather than until this
                // request answers: the button says "stopping", and the sweep
                // only stops at its next poll.
                setStoppingGeocode(true);
                cancelGeocode.mutate(undefined, { onError: () => {} });
              }}>
              {stoppingGeocode ? t("app.stopping") : t("app.stop")}
            </Button>
          </div>
          <ProgressBar
            done={geocodeProgress?.done ?? 0}
            total={geocodeProgress?.total ?? 0}
            indeterminate={!geocodeProgress || geocodeProgress.total <= 0}>
            {geocodeProgress
              ? t("maintenance.geocodeProgress", {
                  done: geocodeProgress.done,
                  total: geocodeProgress.total,
                  geocoded: geocodeProgress.geocoded,
                  cached: geocodeProgress.cached,
                }) +
                (geocodeProgress.not_found > 0
                  ? t("maintenance.geocodeProgressNotFound", { count: geocodeProgress.not_found })
                  : "")
              : t("maintenance.geocodeStarting")}
            {" "}
            <span className="opacity-75 font-normal">{t("maintenance.geocodePacing")}</span>
            {geocodeProgress?.last_error && (
              <span className="block opacity-75 font-normal text-negative-ink">
                {t("maintenance.geocodeLastIssue", { error: geocodeProgress.last_error })}
              </span>
            )}
          </ProgressBar>
        </div>
      )}

      {cacheCleared !== null && (
        <div className="p-3.5 rounded-xl bg-neutral-tint border border-neutral-line text-xs text-ink-strong flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <p>
            {cacheCleared === 0
              ? t("maintenance.cacheClearedNone")
              : t(cacheCleared === 1 ? "maintenance.cacheClearedOne" : "maintenance.cacheCleared", {
                  count: cacheCleared,
                })}
          </p>
          <IconButton data-action="maintenance.cacheCleared.dismiss"
            variant="ghost" size="sm" className="shrink-0"
            label={t("common.close")}
            onClick={() => clearCache.reset()}>
            <Close size={16} />
          </IconButton>
        </div>
      )}

      {geocodeResult && !geocoding && (
        <div className="p-3.5 rounded-xl bg-info-tint border border-info-line text-xs text-ink-strong flex items-start justify-between gap-3 animate-fade-in shadow-sm">
          <div className="space-y-1">
            <p className="font-semibold text-info-ink-strong text-sm flex items-center gap-1.5">
              <Place /> {t("maintenance.geocodeDone")}
            </p>
            {geocodeResult.scanned === 0 ? (
              <p>{t("maintenance.geocodeNothing")}</p>
            ) : (
              <p>
                {t("maintenance.geocodeLocated", {
                  geocoded: geocodeResult.geocoded,
                  scanned: geocodeResult.scanned,
                })}
                {geocodeResult.not_found > 0 &&
                  t("maintenance.geocodeNotFound", { count: geocodeResult.not_found })}
                .
                {geocodeResult.cancelled ? (
                  <span className="block mt-1 font-medium text-caution-ink">
                    {t("maintenance.geocodeCancelled")}
                  </span>
                ) : geocodeResult.remaining > 0 ? (
                  <> {t("maintenance.geocodeRemaining", { count: geocodeResult.remaining })}</>
                ) : null}
              </p>
            )}
          </div>
          <IconButton data-action="maintenance.result.dismiss"
            variant="ghost" size="sm" className="shrink-0"
            label={t("common.close")}
            onClick={() => geocode.reset()}>
            <Close size={16} />
          </IconButton>
        </div>
      )}
    </Card>
  );
}
