/** What the dashboard hands to whatever the URL has opened on top of it.
 *
 *  The overlays are routes now, so the router renders them rather than `App`
 *  — but the grid behind them still holds the rows, the tag list and the writes,
 *  and two components asking the backend the same question separately is how a
 *  property comes to be starred in one place and not in the other. React
 *  Router's outlet context is the way back to the parent that already has it.
 */
import { useOutletContext } from "react-router-dom";
import type { Property, Settings, Tag } from "../types";

export interface DashboardContext {
  /** The rows the grid is holding. A property opened from one of them needs no
   *  request of its own; one opened from a pasted link is not in here, and
   *  fetches itself. */
  properties: Property[];
  tags: Tag[];
  settings: Settings | null;
  toggleFavorite: (property: Property) => void;
  addTag: (property: Property, name: string) => void;
  removeTag: (property: Property, tagId: number) => void;
  /** Show this property on the map, and close what is over it. */
  showOnMap: (property: Property) => void;
  /** Back to the grid, with the filters intact. */
  close: () => void;
}

export function useDashboard(): DashboardContext {
  return useOutletContext<DashboardContext>();
}
