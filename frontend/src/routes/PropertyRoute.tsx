/** One property, at its own address.
 *
 *  `/listings/123` is the whole of what this route needs: the id comes from the
 *  path and the filters behind it from the query string, so the page can be
 *  linked, bookmarked, reopened in a second tab, and pointed at from a
 *  notification. Which is the reason for the fetch below — the grid holds the
 *  row whenever the user clicked a card to get here, and holds nothing at all
 *  when they arrived from somewhere else.
 */
import { useRef } from "react";
import { Navigate, useLocation, useParams } from "react-router-dom";
import PropertyModal from "../components/PropertyModal";
import { useProperty } from "../queries/properties";
import type { Property } from "../types";
import { useDashboard } from "./context";
import { LISTINGS, withSearch } from "./params";

export default function PropertyRoute() {
  const { id } = useParams();
  const propertyId = Number(id);
  const known = Number.isInteger(propertyId);
  const location = useLocation();
  const {
    properties, tags, settings, toggleFavorite, addTag, removeTag, showOnMap, close,
  } = useDashboard();

  const inGrid = properties.find((p) => p.id === propertyId) ?? null;
  const fetched = useProperty(propertyId, known && inGrid === null);

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
  // The first paint of a cold open, with the request still in flight: the grid
  // is already behind this, so there is nothing to stand in for.
  if (!property) return null;

  return (
    <PropertyModal
      property={property}
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
