/** The other half of the grid: the same filtered set, placed.
 *
 *  The tiles are the one address the app asks for that the harness will not let
 *  it have, and that is deliberate on both sides — see `expectBlocked`. What is
 *  asserted here is everything the map owes the user without a backdrop: the
 *  pins, the note about the listings it cannot place, and the way back.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, waitForResults } from "./harness/dashboard";

const TILES = /tile\.openstreetmap\.org/;

test("the map shows the filtered set and the grid comes back", async ({
  page,
  offlineGuard,
}) => {
  offlineGuard.expectBlocked(TILES);

  await page.goto("/");
  await waitForResults(page);

  // A card the map can actually place: the ones flagged "not on map" have no
  // coordinates, and looking for their pin would be looking for the bug.
  const placed = cards(page).filter({ hasNotText: "not on map" }).first();
  const title = (await placed.getAttribute("aria-label")) ?? "";

  const view = page.getByRole("group", { name: "View" });
  await view.getByRole("button", { name: "🗺 Map" }).click();

  // The map says how much of the set it is showing, and how much it cannot
  // place. About a sixth of the corpus has no coordinates on purpose, because
  // the portals omit them and a map that quietly drops those listings is how a
  // user loses one.
  const summary = page.getByText(/\d+ of \d+ properties on the map/);
  await expect(summary).toBeVisible();
  const counted = (await summary.innerText()).match(/(\d+) of (\d+) properties on the map/);
  const shown = Number(counted?.[1]);
  const total = Number(counted?.[2]);
  expect(shown).toBeGreaterThan(0);
  expect(shown).toBeLessThan(total);
  await expect(page.getByText(`${total - shown} without coordinates`)).toBeVisible();

  // The pins themselves: each marker carries its property's title, so finding
  // one is proof the corpus was placed and not merely counted.
  await expect(page.getByTitle(title).first()).toBeVisible();
  await expect(cards(page)).toHaveCount(0);
  await checkScreen(page, "the map");

  await view.getByRole("button", { name: "▦ Grid" }).click();
  await waitForResults(page);
  await expect(summary).toBeHidden();
});
