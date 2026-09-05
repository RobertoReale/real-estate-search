/** One property, at its own address.
 *
 *  `/listings/123` is the whole of what this route needs: the id comes from the
 *  path and the filters behind it from the query string, so the page can be
 *  linked, bookmarked, reopened in a second tab, and pointed at from a
 *  notification. Which is the reason for the fetch below — the grid holds the
 *  row whenever the user clicked a card to get here, and holds nothing at all
 *  when they arrived from somewhere else.
 *
 *  This file decides *which* property is on screen and how the user moves
 *  between them; `PropertyDetail` decides what that looks like.
 */
import { useCallback, useEffect, useRef } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { DESKTOP_QUERY, useMediaQuery } from "../../hooks/useMediaQuery";
import { useT } from "../../i18n";
import { useProperty } from "../../queries/properties";
import type { Property } from "../../types";
import { Skeleton } from "../../ui";
import { useDashboard } from "../context";
import { LISTINGS, propertyPath, withSearch } from "../params";
import PropertyDetail from "./PropertyDetail";
import { neighbours } from "./neighbours";

/** The keys that move through the set. `j`/`k` because the hands are already
 *  there, the arrows because that is what everybody tries first. */
const FORWARD = ["j", "ArrowRight", "ArrowDown"];
const BACK = ["k", "ArrowLeft", "ArrowUp"];

export default function PropertyRoute() {
  const t = useT();
  const { id } = useParams();
  const propertyId = Number(id);
  const known = Number.isInteger(propertyId);
  const location = useLocation();
  const navigate = useNavigate();
  const page = useMediaQuery(DESKTOP_QUERY);
  const {
    properties, tags, settings, toggleFavorite, addTag, removeTag, showOnMap, close,
  } = useDashboard();

  const inGrid = properties.find((p) => p.id === propertyId) ?? null;
  const fetched = useProperty(propertyId, known && inGrid === null);
  const near = neighbours(properties, propertyId);

  /** Moving to the neighbour *replaces* the entry rather than pushing one.
   *
   *  Twenty properties read one after another would otherwise be twenty steps
   *  of history, and Back — which the user presses to mean "return to my
   *  results" — would walk them all again in reverse. One entry per visit to
   *  the detail, whatever is read while inside it. */
  const go = useCallback(
    (next: number) =>
      navigate(withSearch(propertyPath(next), location.search), { replace: true }),
    [navigate, location.search],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      // Typing "j" into the notes is typing, not navigating.
      const from = event.target as HTMLElement | null;
      if (from?.closest("input, textarea, select, [contenteditable='true']")) return;

      const wanted = FORWARD.includes(event.key)
        ? near.next
        : BACK.includes(event.key)
          ? near.previous
          : undefined;
      // Not a traversal key, or one with nothing on that side: leave the key
      // alone rather than swallow the page's own scrolling.
      if (wanted === undefined || wanted === null) return;
      event.preventDefault();
      go(wanted);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, near.next, near.previous]);

  // The copy it was opened with stays on screen while a newer one is on its way.
  // A property can leave the filtered set while its own detail is open — a
  // favourite toggled under the favourites filter does it — and closing the thing the
  // user is reading, to reopen it a moment later, reads as the app losing its
  // place. Same reasoning as the grid's `lastAnswer`: an answer that did arrive
  // beats a blank.
  const shown = useRef<Property | null>(null);
  const current = inGrid ?? fetched.data ?? null;
  if (current) shown.current = current;
  const property = current ?? (shown.current?.id === propertyId ? shown.current : null);

  // An id that names nothing — a mistyped link, or a property deleted since the
  // link was sent. The dashboard is the honest place to land, and `replace` so
  // Back does not bounce straight back into the same dead address.
  if (!known || (fetched.isError && property === null)) {
    return <Navigate to={withSearch(LISTINGS, location.search)} replace />;
  }
  // The first paint of a cold open, with the request still in flight. In the
  // sheet the grid is still behind it and there is nothing to stand in for; on
  // the page the grid has given up the screen, so the shape of what is coming
  // goes there instead of a blank one.
  if (!property) {
    return page
      ? (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Skeleton className="aspect-[16/10] w-full" label={t("common.loading")} />
          <Skeleton className="h-32 w-full" />
        </div>
      )
      : null;
  }

  return (
    <PropertyDetail
      property={property}
      page={page}
      neighbours={near}
      onGo={go}
      onClose={close}
      onDeleted={close}
      onToggleFavorite={() => toggleFavorite(property)}
      onShowOnMap={showOnMap}
      allTags={tags}
      onAddTag={(name) => addTag(property, name)}
      onRemoveTag={(tagId) => removeTag(property, tagId)}
      auditEnabled={settings?.listing_audit_enabled ?? false}
    />
  );
}
