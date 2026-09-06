/** The guided first run.
 *
 *  Three steps and the rules that order them. Nothing outside this directory
 *  needs the steps themselves — `router.tsx` needs the screen, and the "/"
 *  route needs `shouldGuide` to decide whether a fresh install opens here or on
 *  the listings.
 */
export { default as OnboardingRoute } from "./OnboardingRoute";
export { shouldGuide } from "./steps";
