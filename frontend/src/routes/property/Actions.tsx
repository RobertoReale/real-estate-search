/** What can be done to a property from its own page.
 *
 *  Two kinds, and the layout says which is which: on the left the two that only
 *  look something up, on the right the ones that take the property out of the
 *  grid. Every one of the second kind asks first and leaves an undo behind it —
 *  a click with no way back is a trap, and "gone" is a verdict the availability
 *  check can reach on a portal redirect it misread.
 */
import { useState } from "react";
import { useT } from "../../i18n";
import {
  useCheckSingleProperty, useGeocodeProperty, useHideProperty, useMarkPropertySold,
  useRestoreProperty,
} from "../../queries/properties";
import type { Property } from "../../types";
import { Button } from "../../ui";
import { Atlas, Hidden, Restore, Sold, Verify } from "../../ui/icons";
import { useToasts } from "../../components/Toast";

interface Props {
  property: Property;
  /** The property has left the grid: back to it, since this page is about a row
   *  that is no longer in the set behind it. */
  onDone: () => void;
  onShowOnMap: (property: Property) => void;
}

export function Actions({ property: p, onDone, onShowOnMap }: Props) {
  const t = useT();
  const toasts = useToasts();
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const hasCoords = p.latitude !== null && p.longitude !== null;

  const locate = useGeocodeProperty();
  const checkOnline = useCheckSingleProperty();
  const restore = useRestoreProperty();
  const markSold = useMarkPropertySold();
  const hide = useHideProperty();

  /** The way back from a close the user regrets. The card is gone from the grid
   *  by the time this is offered, so the undo is the id and the endpoint, not
   *  anything held on screen. */
  function undoClose() {
    return {
      label: t("toast.undo"),
      run: async () => {
        try {
          await restore.mutateAsync(p.id);
        } catch (e) {
          toasts.fail(e, { doing: t("toast.undoFailed") });
        }
      },
    };
  }

  async function viewOnMap() {
    // Already placed: jump straight to the pin.
    if (hasCoords) {
      onShowOnMap(p);
      return;
    }
    // No coordinates yet — resolve them on demand (portals omit them ~70% of
    // the time), then show the map. Fail-open: an address too vague to place
    // is not an error, it just leaves the property off the map.
    try {
      // The mutation invalidates the grid, so the new pin is in the set the map
      // reads by the time it renders — nothing has to be handed upwards.
      const { located } = await locate.mutateAsync(p.id);
      if (located) {
        onShowOnMap(p);
      } else {
        // Nothing broke: the address is simply not specific enough to place, so
        // there is nothing to retry and nothing to advise.
        toasts.show({ tone: "error", text: t("detail.locateFailed") });
      }
    } catch (e) {
      toasts.fail(e, { doing: t("detail.locateError"), retry: () => viewOnMap() });
    }
  }

  async function checkIfOnline() {
    setCheckResult(null);
    try {
      const { summary } = await checkOnline.mutateAsync(p.id);
      if (summary.gone > 0) {
        setCheckResult(t("detail.checkGone"));
      } else if (summary.online > 0) {
        setCheckResult(t("detail.checkOnline"));
      } else {
        setCheckResult(t("detail.checkUnknown"));
      }
    } catch (e) {
      toasts.fail(e, { doing: t("detail.checkError"), retry: () => checkIfOnline() });
    }
  }

  const discarded = p.status === "hidden" || p.status === "gone" || p.status === "sold";

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button data-action="detail.checkOnline"
          size="sm"
          disabled={checkOnline.isPending || !p.listings.length}
          onClick={checkIfOnline}
          title={t("detail.checkOnlineTitle")}>
          <Verify />
          {checkOnline.isPending ? t("app.checking") : t("detail.checkOnlineButton")}
        </Button>
        <Button data-action="detail.viewOnMap"
          size="sm"
          disabled={locate.isPending}
          onClick={viewOnMap}
          title={t(hasCoords ? "detail.viewOnMapTitle" : "detail.locateAndViewTitle")}>
          <Atlas />
          {locate.isPending ? t("maintenance.locating") : t("detail.viewOnMap")}
        </Button>
        {checkResult && (
          <span className="text-xs font-medium animate-fade-in">{checkResult}</span>
        )}
      </div>
      {discarded ? (
        <button data-action="detail.restore"
          className="inline-flex items-center gap-1.5 accent-good hover:opacity-80
            text-sm transition"
          onClick={async () => {
            // The availability check fails open (invariant 16), but a portal
            // redirect or block it misread as removal can still mark a live
            // listing "gone" — this is the way back for that case, a manual
            // "Hide", and a mistaken "Mark sold".
            const msg = t(
              p.status === "gone"
                ? "detail.restoreGone"
                : p.status === "sold"
                  ? "detail.restoreSold"
                  : "detail.restoreHidden",
            );
            if (confirm(msg)) {
              try {
                await restore.mutateAsync(p.id);
                onDone(); // the grid re-reads itself; this leaves the page
              } catch (e) {
                toasts.fail(e, { doing: t("detail.restoreFailed") });
              }
            }
          }}>
          <Restore /> {t("detail.restore")}
        </button>
      ) : (
        <div className="flex items-center gap-3">
          <button data-action="detail.markSold"
            className="inline-flex items-center gap-1.5 text-caution-ink
              hover:opacity-80 text-sm transition"
            onClick={async () => {
              // "sold" is a confirmed market close: it leaves the grid like
              // "hidden" but is kept as a real sale date feeding the
              // market-velocity signals. For the "VENDUTO" re-posts that stay
              // online for weeks and never leave on their own.
              const msg = t(
                p.contract === "rent" ? "detail.confirmRented" : "detail.confirmSold",
              );
              if (confirm(msg)) {
                try {
                  await markSold.mutateAsync(p.id);
                  onDone();
                  toasts.done(t("toast.sold"), undoClose());
                } catch (e) {
                  toasts.fail(e, { doing: t("detail.markSoldFailed") });
                }
              }
            }}>
            <Sold /> {t(p.contract === "rent" ? "detail.markRented" : "detail.markSold")}
          </button>
          <button data-action="detail.hide"
            className="inline-flex items-center gap-1.5 accent-bad hover:opacity-80
              text-sm transition"
            onClick={async () => {
              // the backend marks as "hidden" rather than physical deletion so
              // subsequent scans do not re-insert or notify it as new
              if (confirm(t("app.confirmHideOne"))) {
                try {
                  await hide.mutateAsync(p.id);
                  onDone();
                  toasts.done(t("toast.hidden"), undoClose());
                } catch (e) {
                  toasts.fail(e, { doing: t("detail.hideFailed") });
                }
              }
            }}>
            <Hidden /> {t("detail.hide")}
          </button>
        </div>
      )}
    </div>
  );
}
