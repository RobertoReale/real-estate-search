/** The capability setup.
 *
 *  Two things leave this directory: the screen, for `router.tsx`, and
 *  `pendingGroups`, for the part of Settings that says which capabilities are
 *  still switched off. The tables themselves stay in `groups.ts`.
 */
export { default as SetupRoute } from "./SetupRoute";
export { pendingGroups, groupTitleKey } from "./groups";
export type { GroupId } from "./groups";
