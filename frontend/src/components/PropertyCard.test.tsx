/** The card is the door to a property's detail — the dashboard's primary flow.
 *
 * It was a bare `<article onClick>`: no focus, no key handling, so opening a
 * listing was available to pointer users only. These tests pin the keyboard
 * path, and the one subtlety that makes it safe — Enter inside a nested
 * control (the ⭐/✕ quick actions live in the same box) must stay that
 * control's, not open the modal on top of it.
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
  omi_zone_code: "", match_score: null,
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
  it("is focusable", () => {
    const card = renderCard(vi.fn());
    card.focus();
    expect(document.activeElement).toBe(card);
  });

  it("opens the property on Enter and on Space", () => {
    const onClick = vi.fn();
    const card = renderCard(onClick);
    fireEvent.keyDown(card, { key: "Enter" });
    fireEvent.keyDown(card, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("leaves Enter alone inside the quick-action buttons", () => {
    // the ⭐ button lives inside the card; a keypress on it must favourite the
    // property, not also open the detail modal behind its own handler
    const onClick = vi.fn();
    renderCard(onClick);
    const favorite = screen.getByRole("button", { name: /favourite|favorite|preferit/i });
    fireEvent.keyDown(favorite, { key: "Enter", bubbles: true });
    expect(onClick).not.toHaveBeenCalled();
  });
});
