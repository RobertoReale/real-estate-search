/** Where a property sits in the list the user is reading it from.
 *
 *  Traversal is over the *filtered, sorted* set the grid is holding, because
 *  that is what "the next result" means to the person pressing the key: next in
 *  what they searched for, not next by id. A property opened from a link whose
 *  filters exclude it is in no list at all, and then there is no next one —
 *  which is why every field below can be null and nothing invents a neighbour.
 */
import type { Property } from "../../types";

export interface Neighbours {
  /** 1-based position in the set, or null when the property is not in it. */
  position: number | null;
  total: number;
  previous: number | null;
  next: number | null;
}

export function neighbours(properties: Property[], id: number): Neighbours {
  const at = properties.findIndex((p) => p.id === id);
  if (at === -1) {
    return { position: null, total: properties.length, previous: null, next: null };
  }
  return {
    position: at + 1,
    total: properties.length,
    previous: at > 0 ? properties[at - 1].id : null,
    next: at < properties.length - 1 ? properties[at + 1].id : null,
  };
}
