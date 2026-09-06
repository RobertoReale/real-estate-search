/** The activity screen: the scan in flight, and the account of the ones before.
 *
 *  Same rule as `routes/searches/`: none of this is reusable. `ScanLive` knows
 *  what a portal page is and `ScanJournal` knows what "blocked" means to a
 *  scraper, and a second screen that wants either of them wants this screen.
 *
 *  `progress.ts` is the exception worth naming: it holds no markup, and it is
 *  where the rule that a proportion may only be drawn against a real total is
 *  written once and unit-tested.
 */
export { default as ActivityRoute } from "./ActivityRoute";
export { default as ScanJournal } from "./ScanJournal";
export { default as ScanLive } from "./ScanLive";
export { outcomeLabel, pageProportion, phaseLabel, worthExplaining } from "./progress";
export type { Proportion } from "./progress";
