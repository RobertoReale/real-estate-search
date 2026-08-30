/** The card is the door to a property's detail — the dashboard's primary flow.
 *
 * It was a bare `<article onClick>`: no focus, no key handling, so opening a
 * listing was available to pointer users only. That was first fixed by making
 * the whole card a `role="button"`, which worked but made the card a widget
 * containing other widgets — the ⭐/✕ quick actions and the tag picker all live
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
  address: "", latitude: null, longitude: null, rooms: 3, floor: "2", sqm: 80,
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
    // the ⭐ button lives inside the card, which opens the property on click;
    // pressing it must favourite the property and nothing else
    const onClick = vi.fn();
    renderCard(onClick);
    fireEvent.click(screen.getByRole("button", { name: /favourite|favorite|preferit/i }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
