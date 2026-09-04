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

const TILES = /tile\.openstreetmap\.org/;

/** The one filter used throughout: a ceiling that narrows the corpus without
 *  emptying it, so a count is always a real one on both sides of a step. */
const CEILING = "900000";

test("the bare address is the listings", async ({ page }) => {
  await page.goto("/");
  await waitForResults(page);
  expect(new URL(page.url()).pathname).toBe("/listings");
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
  // address. The property is open, and the grid behind it is the sender's.
  const fresh = await page.context().newPage();
  await fresh.goto(shared.href);
  await expect(fresh.getByRole("heading", { level: 2, name: title })).toBeVisible();
  await expect(fresh.getByLabel(/^Max price €/)).toHaveValue(CEILING);
  await expect.poll(() => resultCount(fresh)).toBe(narrowed);
  await fresh.close();
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
  await expect(cards(page)).toHaveCount(0);
  await checkScreen(page, "a property opened from a link that excludes it");

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
  const favorites = page.getByLabel("⭐ Favorites");

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
  await page.getByRole("group", { name: "View" }).getByRole("button", { name: "🗺 Map" }).click();
  await expect(onTheMap).toBeVisible();

  await page.reload();

  // The filter, the sort and the view are all where they were left: the reload
  // read them off the address rather than out of a memory the reload emptied.
  await expect(page.getByLabel(/^Max price €/)).toHaveValue(CEILING);
  await expect(page.getByLabel("Sort by")).toHaveValue("price_asc");
  await expect(onTheMap).toBeVisible();
  await expect.poll(() => resultCount(page)).toBe(narrowed);
});
