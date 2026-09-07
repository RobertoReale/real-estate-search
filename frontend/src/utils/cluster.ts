/** Grouping map pins that are too close together to be separate pins.
 *
 *  Above a few hundred listings a city centre stops being a set of addresses
 *  and becomes one blue smear: the pins overlap, the one on top is whichever
 *  Leaflet drew last, and hovering picks a listing at random. Grouping them
 *  gives the reader the number instead — "47 here" is a fact, a smear is not —
 *  and clicking a group zooms until it comes apart.
 *
 *  The grid is measured **in screen pixels at the zoom being drawn**, not in
 *  degrees, which is the whole reason `project` is a parameter rather than a
 *  little trigonometry in here. A fixed span in degrees clusters a whole
 *  province at zoom 15 and nothing at all at zoom 5; a fixed span in pixels
 *  means "closer together than a pin is wide", which is the thing actually
 *  being fixed, and it re-forms on every zoom because the projection changed.
 *  Leaflet's `map.project(latlng, zoom)` is exactly that function, and passing
 *  it in keeps this module free of Leaflet — so it is testable without a DOM.
 */

/** Anything with a place on the map. The map's own pins carry a lot more; this
 *  is the part the grouping reads. */
export interface Placed {
  lat: number;
  lng: number;
}

/** A point on the pixel plane of one zoom level. */
export interface Point {
  x: number;
  y: number;
}

export type Project = (lat: number, lng: number) => Point;

export interface Cluster<T extends Placed> {
  /** Where the group is drawn. A single member is drawn on its own coordinate,
   *  exactly where it would have been without any grouping at all; a group is
   *  drawn at the mean of its members, which sits inside the cell and so cannot
   *  wander away from the pins it stands for. */
  lat: number;
  lng: number;
  items: T[];
}

/** Buckets `items` into a square grid `cellPx` wide, laid over the pixel plane
 *  `project` describes.
 *
 *  Order is preserved twice over: the groups come back in the order their first
 *  member appeared, and each group holds its members in input order. A map that
 *  reshuffles its pins between two identical renders is one whose tooltips move
 *  under the pointer.
 *
 *  A point that cannot be projected to a finite pixel — which is what a NaN
 *  coordinate becomes — is dropped rather than bucketed, because every one of
 *  them hashes to the same cell and a single bad row would otherwise swallow
 *  the whole city into one group of "1 200 properties here".
 */
export function clusterByGrid<T extends Placed>(
  items: readonly T[],
  project: Project,
  cellPx: number,
): Cluster<T>[] {
  if (!(cellPx > 0)) throw new RangeError("cellPx must be a positive number of pixels");

  const cells = new Map<string, T[]>();
  for (const item of items) {
    const { x, y } = project(item.lat, item.lng);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const key = `${Math.floor(x / cellPx)}:${Math.floor(y / cellPx)}`;
    const cell = cells.get(key);
    if (cell) cell.push(item);
    else cells.set(key, [item]);
  }

  const out: Cluster<T>[] = [];
  for (const group of cells.values()) {
    if (group.length === 1) {
      out.push({ lat: group[0].lat, lng: group[0].lng, items: group });
      continue;
    }
    let lat = 0;
    let lng = 0;
    for (const item of group) {
      lat += item.lat;
      lng += item.lng;
    }
    out.push({ lat: lat / group.length, lng: lng / group.length, items: group });
  }
  return out;
}
