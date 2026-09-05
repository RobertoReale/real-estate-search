/** The address bar, as the state of the app.
 *
 *  Everything here is a thing a user does with a browser rather than with this
 *  application: send someone a link, press Back, reload the page. None of them
 *  worked before the dashboard had URLs — a property could not be linked, Back
 *  left the app entirely, and a reload dropped the filters — and none of them is
 *  visible to a test that only ever clicks forwards, which is why they get a
 *  spec of their own.
 */
import { checkScreen, expect, test } from "./fixtures";
import { cards, resultCount, waitForResults } from "./harness/dashboard";
import { press } from "./harness/drive";

const TILES = /tile\.openstreetmap\.org/;

/** The one filter used throughout: a ceiling that narrows the corpus without
 *  emptying it, so a count is always a real one on both sides of a step. */
const CEILING = "900000";

test("the bare address is the listings", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  expect(new URL(page.url()).pathname).toBe("/listings");
});

test("the four places are linkable, and keep the filters between them", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  await page.getByLabel(/^Max price €/).fill(CEILING);
  await expect.poll(() => new URL(page.url()).searchParams.get("max_price")).toBe(CEILING);

  // Going somewhere else and coming back is not a filter change. The query
  // string is the app's state and the navigation carries it, so the listings
  // are still narrowed rather than reset to the whole corpus.
  for (const [id, pathname] of [
    ["nav.insights", "/insights"],
    ["nav.searches", "/searches"],
    ["nav.listings", "/listings"],
  ] as const) {
    await press(page, id);
    await expect.poll(() => new URL(page.url()).pathname).toBe(pathname);
    expect(new URL(page.url()).searchParams.get("max_price")).toBe(CEILING);
  }
  await expect(page.getByLabel(/^Max price €/)).toHaveValue(CEILING);

  // The fourth is a dialog over the listings rather than a screen beside them,
  // so it goes last: nothing underneath it can be pressed while it is open.
  await press(page, "nav.settings");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/settings");
  expect(new URL(page.url()).searchParams.get("max_price")).toBe(CEILING);

  // …and each address opens on its own, which is what makes it a place rather
  // than a panel: a link to the insights has to work in a tab that has never
  // seen the listings.
  await page.goto("/insights");
  await expect(page.locator("[data-action='trends.toggle']")).toBeVisible();
  await checkScreen(page, "the insights");

  await page.goto("/searches");
  await expect(page.locator("[data-action='profiles.row.select']").first()).toBeVisible();
  await checkScreen(page, "the searches");
});

test("a property's link opens it cold, carrying the filters it was sent with", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  await page.getByLabel(/^Max price €/).fill(CEILING);
  await expect.poll(() => resultCount(page)).toBeLessThan(all);
  const narrowed = await resultCount(page);

  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";
  expect(title).not.toBe("");
  await card.click();
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();

  // This is the thing a user copies out of the address bar: the property in the
  // path, what they had narrowed to in the query string.
  const shared = new URL(page.url());
  expect(shared.pathname).toMatch(/^\/listings\/\d+$/);
  expect(shared.searchParams.get("max_price")).toBe(CEILING);

  // …and pasted into a fresh tab, which shares nothing with this one but the
  // address. The property opens on its own, and the grid it closes onto is the
  // sender's rather than the recipient's default — the query string was carried
  // through a screen that never showed it.
  const fresh = await page.context().newPage();
  await fresh.goto(shared.href);
  await expect(fresh.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await press(fresh, "detail.close");
  await expect(fresh.getByLabel(/^Max price €/)).toHaveValue(CEILING);
  await expect.poll(() => resultCount(fresh)).toBe(narrowed);
  await fresh.close();
});

test("Back from a property returns to the grid where it was left", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);

  // Far enough down that the grid's own top is nowhere near: a restore that
  // quietly landed at zero would pass against the second row.
  const deep = cards(page).nth(20);
  await deep.scrollIntoViewIfNeeded();
  const left = await page.evaluate(() => window.scrollY);
  expect(left).toBeGreaterThan(0);

  await deep.click();
  await expect(page.getByRole("heading", { level: 2 }).first()).toBeVisible();
  // The property is a screen of its own, so it opens at its own top rather than
  // at whatever offset the reader had scrolled the grid to.
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  await page.goBack();
  await waitForResults(page);
  // Within a row of where it was: the cards are the same height they were, but
  // the images behind them are not necessarily decoded again at the same moment.
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThan(left - 200);
});

test("a property the grid cannot answer for still opens, and a made-up one does not", async ({
  page,
}) => {
  await page.goto("/");
  await waitForResults(page);
  const card = cards(page).first();
  const title = (await card.getAttribute("aria-label")) ?? "";
  await card.click();
  const id = new URL(page.url()).pathname.split("/").pop();

  // The recipient's filters exclude it — the corpus is one city, so this one
  // matches nothing at all. A link that only worked when the reader happened to
  // be looking at the same grid would not be a link.
  await page.goto(`/listings/${id}?city=Bologna`);
  await expect(page.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await checkScreen(page, "a property opened from a link that excludes it");
  // The filters really were honoured on the way in: closing lands on the empty
  // grid they describe, rather than on the recipient's own listings.
  await press(page, "detail.close");
  await expect(cards(page)).toHaveCount(0);

  // An id that names nothing: a mistyped link, or a property gone since it was
  // sent. The dashboard is where that lands, rather than a blank screen.
  await page.goto("/listings/99999999");
  await waitForResults(page);
  expect(new URL(page.url()).pathname).toBe("/listings");
});

test("Back and Forward move through filter changes", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  const ceiling = page.getByLabel(/^Max price €/);
  const favorites = page.getByRole("checkbox", { name: "Favorites", exact: true });

  await ceiling.fill(CEILING);
  await expect.poll(() => resultCount(page)).toBeLessThan(all);
  const narrowed = await resultCount(page);

  await favorites.check();
  await expect.poll(() => new URL(page.url()).searchParams.get("only_favorites")).toBe("1");

  // Back through them one at a time. Each step is a decision the user made, not
  // a keystroke: typing a price is one entry however many digits it took.
  await page.goBack();
  await expect(favorites).not.toBeChecked();
  await expect(ceiling).toHaveValue(CEILING);
  await expect.poll(() => resultCount(page)).toBe(narrowed);

  await page.goBack();
  await expect(ceiling).toHaveValue("");
  await expect.poll(() => resultCount(page)).toBe(all);

  await page.goForward();
  await expect(ceiling).toHaveValue(CEILING);
  await expect.poll(() => resultCount(page)).toBe(narrowed);

  await page.goForward();
  await expect(favorites).toBeChecked();
});

test("a reload keeps the grid where it was", async ({ page, offlineGuard }) => {
  offlineGuard.expectBlocked(TILES);

  await page.goto("/");
  await waitForResults(page);
  const all = await resultCount(page);

  await page.getByLabel(/^Max price €/).fill(CEILING);
  await page.getByLabel("Sort by").selectOption("price_asc");
  await expect.poll(() => resultCount(page)).toBeLessThan(all);
  const narrowed = await resultCount(page);

  const onTheMap = page.getByText(/\d+ of \d+ properties on the map/);
  await page.getByRole("group", { name: "View" }).getByRole("button", { name: "Map" }).click();
  await expect(onTheMap).toBeVisible();

  await page.reload();

  // The filter, the sort and the view are all where they were left: the reload
  // read them off the address rather than out of a memory the reload emptied.
  await expect(page.getByLabel(/^Max price €/)).toHaveValue(CEILING);
  await expect(page.getByLabel("Sort by")).toHaveValue("price_asc");
  await expect(onTheMap).toBeVisible();
  await expect.poll(() => resultCount(page)).toBe(narrowed);
});
