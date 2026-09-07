/** The other half of the grid: the same filtered set, placed — and beside it,
 *  still, the cards. A pin says where a property is and can say nothing else;
 *  the list says what it is. Splitting the view is what lets one question be
 *  asked of both at once, and the hover is how a pin and a card admit to being
 *  the same property.
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
  await view.getByRole("button", { name: "Map" }).click();

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
  const pin = page.getByTitle(title).first();
  await expect(pin).toBeVisible();

  // The cards did not go anywhere: the map is beside the list, not instead of
  // it, and the listings without coordinates are still readable here.
  await expect(placed).toBeVisible();
  await expect(cards(page).first()).toBeVisible();

  // Drawing is three clicks and none of them is a button, so the map says which
  // three before the first one — otherwise the tool is a mode with no
  // instructions, and the way out of it is guesswork.
  await expect(page.getByText("Draw a radius or an area")).toBeVisible();

  await checkScreen(page, "the map");

  await view.getByRole("button", { name: "▦ Grid" }).click();
  await waitForResults(page);
  await expect(summary).toBeHidden();
});

test("pointing at one half of the map view marks the other", async ({
  page,
  offlineGuard,
}) => {
  offlineGuard.expectBlocked(TILES);

  await page.goto("/");
  await waitForResults(page);
  const placed = cards(page).filter({ hasNotText: "not on map" }).first();
  const title = (await placed.getAttribute("aria-label")) ?? "";

  await page.getByRole("group", { name: "View" }).getByRole("button", { name: "Map" }).click();
  const pin = page.getByTitle(title).first();
  await expect(pin).toBeVisible();

  // List to map: the card is pointed at, and out of a few dozen identical dots
  // exactly one grows — the one that is this listing.
  await placed.hover();
  const lit = page.locator(".leaflet-marker-icon.is-hovered");
  await expect(lit).toHaveCount(1);
  await expect(lit).toHaveAttribute("title", title);

  // Nothing is being pointed at, so nothing is marked. Asserted in the middle
  // because it is what makes the next step mean anything: without it, a card
  // still marked from the step above would pass the assertion below by itself.
  await page.mouse.move(2, 2);
  await expect(page.locator("[data-hovered]")).toHaveCount(0);
  await expect(lit).toHaveCount(0);

  // Map to list: a pin is pointed at, and its card is marked — and brought into
  // view, which for a set this size means it was already there.
  await pin.hover();
  await expect(placed).toHaveAttribute("data-hovered", "true");
});
