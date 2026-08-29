/** The benchmark panel: what it shows, and what it must never show bare.
 *
 * Only visible in a rendered tree, and each assertion guards something that
 * disappears silently. The attribution is required by the licence on the OMI
 * supply, so a refactor that drops the line is a licensing defect and not a
 * cosmetic one — and nothing else in the suite would notice, because the figures
 * themselves would still be right. The staleness badge is the same shape of
 * problem in reverse: without it a two-year-old band renders identically to a
 * current one, which is precisely the silent trust this feature exists to end.
 */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import PropertyModal from "./PropertyModal";
import { I18nProvider, STORAGE_KEY } from "../i18n";
import type { Property } from "../types";

// Pinned rather than left to the default: thousands separators are locale-bound
// ("9,000" here, "9.000" in Italian), and a test that reads them must say which
// language it is asserting in.
beforeEach(() => localStorage.setItem(STORAGE_KEY, "en"));

const BASE = {
  id: 1, title: "Trilocale", city: "Milano", zone: "Centro", address: "",
  latitude: null, longitude: null, rooms: 3, floor: "2", sqm: 100,
  contract: "sale", current_min_price: 1000000, first_price: 1000000,
  image_url: "", status: "active", filtered_reason: "", source: "scan",
  is_favorite: false, notes: "", area_median_sqm_price: 9000,
  area_median_scope: "zone", sqm_price_delta_pct: 11.1,
  omi_min_sqm_price: null, omi_max_sqm_price: null, omi_semester: null,
  omi_stale: false, omi_zone_code: "", match_score: null, deal_score: null,
  deal_label: null, deal_reasons: null, expected_discount_pct: null,
  target_price_low: null, target_price_high: null,
  first_seen_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:00:00Z",
  sold_at: null, listings: [], price_history: [], tags: [], found_by: [],
  commutes: [],
} satisfies Property;

/** A property carrying a band, dated by the caller. */
function withBand(semester: string, stale: boolean): Property {
  return {
    ...BASE,
    omi_min_sqm_price: 8700, omi_max_sqm_price: 20000,
    omi_semester: semester, omi_stale: stale, omi_zone_code: "B12",
  };
}

const noop = () => {};

function show(property: Property): string {
  const { container } = render(
    <I18nProvider>
      <PropertyModal property={property} onClose={noop} onDeleted={noop}
        onToggleFavorite={noop} onNotesSaved={noop} onShowOnMap={noop}
        allTags={[]} onAddTag={noop} onRemoveTag={noop} auditEnabled={false} />
    </I18nProvider>,
  );
  return container.textContent ?? "";
}

describe("the OMI half of the benchmark panel", () => {
  it("dates the band and credits the source", () => {
    const text = show(withBand("2025/2", false));
    expect(text).toContain("8,700–20,000");
    // The semester, spelled as a date rather than as the Agenzia writes it.
    expect(text).toContain("2nd half 2025");
    expect(text).toContain("Fonte: Agenzia Entrate – OMI");
  });

  it("marks a band that has stopped being current", () => {
    expect(show(withBand("2022/2", true))).toContain("out of date");
  });

  it("leaves a current band unmarked", () => {
    expect(show(withBand("2025/2", false))).not.toContain("out of date");
  });

  it("credits nobody when there is no band to credit", () => {
    // The median alone still renders — an attribution beside it would name a
    // source this property never used.
    const text = show(BASE);
    expect(text).toContain("9,000");
    expect(text).not.toContain("Fonte: Agenzia Entrate");
  });

  it("explains the staleness rather than only flagging it", () => {
    render(
      <I18nProvider>
        <PropertyModal property={withBand("2022/2", true)} onClose={noop}
          onDeleted={noop} onToggleFavorite={noop} onNotesSaved={noop}
          onShowOnMap={noop} allTags={[]} onAddTag={noop} onRemoveTag={noop}
          auditEnabled={false} />
      </I18nProvider>,
    );
    expect(screen.getByTitle(/more than 18 months old/i)).toBeTruthy();
  });
});
