/** The searches screen, in the pieces it is actually made of.
 *
 *  Same rule as `routes/listings/`: none of these is reusable and none of them
 *  should be. A health chip knows what `last_run_status` means and a channel
 *  banner knows that a search can ask for Telegram — the moment a second screen
 *  wants one, the right answer is for that screen to be this one.
 *
 *  The forms and the list are still under `components/searchProfiles/` because
 *  they are the panel this page grew out of; what lives here is what the page
 *  itself added when it stopped being the top of somebody else's screen.
 */
export { default as ChannelBanner, unmetChannels } from "./ChannelBanner";
export { default as ProfileHealth } from "./ProfileHealth";
export { default as SearchesRoute } from "./SearchesRoute";
export { needsAttention, profileHealth } from "./health";
export type { Health, HealthInput, HealthState } from "./health";
