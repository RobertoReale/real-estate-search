/** The card is the door to a property's detail — the dashboard's primary flow.
 *
 * It was a bare `<article onClick>`: no focus, no key handling, so opening a
 * listing was available to pointer users only. That was first fixed by making
 * the whole card a `role="button"`, which worked but made the card a widget
 * containing other widgets — the favourite and hide quick actions and the tag
 * picker all live
 * inside it, and a control that contains controls is ambiguous to a screen
 * reader. The door is now the title button, and Enter and Space come from the
 * platform rather than from a key handler of ours.
 *
 * These tests pin what a user gets: a focusable, named way in, and quick
 * actions that stay their own.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PropertyCard from "./PropertyCard";
import type { Property } from "../types";

const PROPERTY = {
  id: 1, title: "Trilocale in Via Test", city: "Milano", zone: "Navigli",
  address: "", latitude: null, longitude: null, coordinate_source: "" as const,
  outside_requested_area: false,
  rooms: 3, floor: "2", sqm: 80,
  contract: "sale", current_min_price: 300000, first_price: 300000,
  image_url: "", status: "active", filtered_reason: "", source: "scan",
  is_favorite: false, notes: "", area_median_sqm_price: null,
  area_median_scope: null, sqm_price_delta_pct: null,
  omi_min_sqm_price: null, omi_max_sqm_price: null, omi_semester: null,
  omi_stale: false, omi_zone_code: "", match_score: null,
  deal_score: null, deal_label: null, deal_reasons: null,
  expected_discount_pct: null, target_price_low: null, target_price_high: null,
  first_seen_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:00:00Z",
  sold_at: null, listings: [], price_history: [], tags: [], found_by: [],
  commutes: [],
} satisfies Property;

function renderCard(onClick: () => void) {
  render(
    <PropertyCard
      property={PROPERTY}
      onClick={onClick}
      onQuickHide={vi.fn()}
      onToggleFavorite={vi.fn()}
      allTags={[]}
      onAddTag={vi.fn()}
      onRemoveTag={vi.fn()}
      goneAfterDays={7}
    />,
  );
  return screen.getByRole("button", { name: PROPERTY.title });
}

describe("PropertyCard keyboard access", () => {
  it("is focusable, and named by the listing", () => {
    const card = renderCard(vi.fn());
    card.focus();
    expect(document.activeElement).toBe(card);
  });

  it("opens the property when its title is activated", () => {
    const onClick = vi.fn();
    // A native <button>: the browser turns Enter and Space into this click, so
    // asserting the click is asserting both keys.
    fireEvent.click(renderCard(onClick));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("is not itself a control containing controls", () => {
    // The whole point of moving the door onto the title: an <article> holding
    // the star, the hide and the tag picker must not also claim to be a button
    // (axe: nested-interactive), or the card and everything in it compete for
    // the same activation.
    renderCard(vi.fn());
    const article = document.querySelector("article");
    expect(article).not.toBeNull();
    expect(article!.getAttribute("role")).toBeNull();
    expect(article!.getAttribute("tabindex")).toBeNull();
  });

  it("leaves the quick-action buttons alone", () => {
    // the favourite button lives inside the card, which opens the property on click;
    // pressing it must favourite the property and nothing else
    const onClick = vi.fn();
    renderCard(onClick);
    fireEvent.click(screen.getByRole("button", { name: /favourite|favorite|preferit/i }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

/** What a card costs when there are a thousand of them.
 *
 *  Nothing here is visible on one card, which is exactly why it is pinned: all
 *  three are the kind of attribute that survives every review because removing
 *  it changes nothing on the screen anyone is looking at, and changes a long
 *  list from a scroll into a slideshow.
 */
describe("PropertyCard on a long list", () => {
  function renderWithPhoto() {
    render(
      <PropertyCard
        property={{ ...PROPERTY, image_url: "https://example.invalid/photo.jpg" }}
        onClick={vi.fn()}
        onQuickHide={vi.fn()}
        onToggleFavorite={vi.fn()}
        allTags={[]}
        onAddTag={vi.fn()}
        onRemoveTag={vi.fn()}
        goneAfterDays={7}
      />,
    );
    return screen.getByRole("img", { name: PROPERTY.title }) as HTMLImageElement;
  }

  it("lets the browser skip it while it is off screen", () => {
    // The grid keeps every result the user has scrolled to, because `j`/`k` and
    // the map's hover both find cards by reading them off the document. What
    // makes that affordable is the browser skipping the ones nobody is looking
    // at, and `.defer-offscreen` (src/index.css) is the whole of how it is
    // asked to. Drop the class and the grid quietly goes back to laying out
    // every card on every frame.
    renderCard(vi.fn());
    expect(document.querySelector("article")).toHaveClass("defer-offscreen");
  });

  it("loads its photo lazily, off the main thread, into a box already its size", () => {
    const img = renderWithPhoto();
    expect(img.getAttribute("loading")).toBe("lazy");
    expect(img.getAttribute("decoding")).toBe("async");
    // The fixed 4:3 frame is what makes the lazy load free: the space is
    // reserved before the bytes arrive, so a photo landing mid-scroll does not
    // shove the rest of the grid down.
    expect(img.parentElement).toHaveClass("aspect-[4/3]");
  });

  it("draws a placeholder rather than a broken image when the photo fails", () => {
    // A listing whose photo has been taken down is ordinary — portals expire
    // them long before the listing goes. The browser's own broken-image glyph
    // in a 4:3 box is the failure a user should never be shown.
    const img = renderWithPhoto();
    fireEvent.error(img);
    expect(screen.queryByRole("img", { name: PROPERTY.title })).toBeNull();
  });
});
