/** The review is only worth reading if it is complete.
 *
 * Its failure mode is silence: a filter added to the builder later gets applied
 * by the scan, changes what comes back, and is mentioned by no line of the
 * screen whose whole job is to say what will be searched. `FIELD_ROW` is typed
 * `Record<keyof SearchProfileParams, ReviewRowId>` so the compiler catches that
 * — but only while the two agree. `SearchProfileParams` is an alias into
 * `types/api.ts`, which is generated from the backend and gated in CI, so this
 * reads that file directly and asks the same question of the text: every
 * property the backend publishes has a row, and every row it names renders.
 *
 * The rest is the two rules that a rendering can break without a type error:
 * "not detected" must not look like "detected as empty", and the two portals
 * must never be collapsed into one verdict.
 */

import { readFileSync } from "node:fs";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { FIELD_ROW, SearchReview } from "./SearchReview";
import { EMPTY_BUILDER } from "./constants";
import { I18nProvider, STORAGE_KEY } from "../../i18n";
import { en } from "../../i18n/en";
import type { SearchBuilderParams, SearchBuilderUrls } from "../../types";

// English, so the assertions can name the sentence they are looking for. Which
// dictionary is active is `i18n.test.ts`'s question, not this file's.
beforeEach(() => localStorage.setItem(STORAGE_KEY, "en"));

/** The properties `SearchBuilderParamsOut` publishes, read out of the generated
 *  file. The block is flat — one property per line at a fixed indent — because
 *  openapi-typescript writes it that way; anything nested would be a shape this
 *  screen could not put on one row anyway. */
function publishedFields(): string[] {
  const source = readFileSync("src/types/api.ts", "utf8").split("\n");
  const start = source.findIndex((line) => line.trim() === "SearchBuilderParamsOut: {");
  expect(start).toBeGreaterThan(-1);
  const fields: string[] = [];
  for (const line of source.slice(start + 1)) {
    if (line === "        };") break;
    const match = /^ {12}(\w+)\??:/.exec(line);
    if (match) fields.push(match[1]);
  }
  return fields;
}

const BUILT: SearchBuilderUrls = {
  immobiliare: "https://www.immobiliare.it/vendita-case/milano/?idMZona[]=10046",
  idealista: "https://www.idealista.it/vendita-case/milano-milano/",
  idealista_zone_page: false,
  idealista_unsupported: [],
  zone_warnings: [],
};

const params = (over: Partial<SearchBuilderParams> = {}): SearchBuilderParams => ({
  ...EMPTY_BUILDER, city: "Milano", ...over,
});

function show(p: SearchBuilderParams, built: Partial<SearchBuilderUrls> = {}) {
  return render(
    <I18nProvider>
      <SearchReview params={p} built={{ ...BUILT, ...built }} confirmed={false}
        setConfirmed={() => {}} verifyZone={() => {}} verifying={false} />
    </I18nProvider>,
  );
}

/** The cell one portal filled in for one criterion. */
function cell(row: string, portal: 0 | 1): HTMLElement {
  const line = document.querySelector(`[data-review-row="${row}"]`);
  expect(line, `no row for ${row}`).not.toBeNull();
  // label, detected, Immobiliare, Idealista — the last two in that order
  return line!.children[2 + portal] as HTMLElement;
}

describe("the review covers every criterion", () => {
  it("gives each field the backend publishes a line of its own", () => {
    const fields = publishedFields();
    // a sanity check on the parse itself: an empty list would make this test
    // pass by finding nothing to check
    expect(fields.length).toBeGreaterThan(15);
    expect(fields).toContain("drawn_area");

    const missing = fields.filter((f) => !(f in FIELD_ROW));
    expect(missing, `no review row for: ${missing.join(", ")}`).toEqual([]);
  });

  it("renders every line those fields were mapped to", () => {
    show(params({ zones: ["Navigli"], zone: "Navigli" }));
    const rendered = new Set(
      [...document.querySelectorAll("[data-review-row]")]
        .map((el) => el.getAttribute("data-review-row")),
    );
    for (const [field, row] of Object.entries(FIELD_ROW)) {
      expect(rendered.has(row), `${field} maps to "${row}", which nothing renders`).toBe(true);
    }
  });
});

describe("nothing is invented", () => {
  it("marks a criterion nothing was read for, rather than leaving it blank", () => {
    show(params());
    // no price in the URL: the line says so in its own words
    const price = document.querySelector('[data-review-row="price"]');
    expect(price?.querySelector("[data-review-undetected]")?.textContent)
      .toBe(en["profiles.review.notDetected"]);
  });

  it("distinguishes it from a criterion read as covering everything", () => {
    show(params());
    const zones = document.querySelector('[data-review-row="zones"]');
    expect(zones?.querySelector("[data-review-undetected]")).toBeNull();
    expect(zones?.textContent).toContain(en["profiles.review.wholeCity"]);
  });

  it("shows a zone id when the id is all there is", () => {
    show(params({ zone_ids: ["10046"] }));
    expect(document.querySelector('[data-review-row="zones"]')?.textContent).toContain("10046");
  });

  it("names a drawn area instead of guessing at a comune", () => {
    show(params({ drawn_area: { kind: "polygon", points: 24, radius_m: 0, lat: null, lng: null } }), {
      immobiliare: "https://www.immobiliare.it/search-list/?vrt=45.44,9.16;45.46,9.16;45.46,9.19",
    });
    const area = document.querySelector('[data-review-row="area"]')?.textContent ?? "";
    // the kind of area and its size, and nowhere a corner coordinate
    expect(area).toContain(en["profiles.review.areaPolygon"].replace("{points}", "24"));
    expect(area).not.toContain("45.44");
  });
});

describe("the two portals are never merged", () => {
  it("calls the same zones exact on one and approximated on the other", () => {
    show(params({ zone: "Navigli", zones: ["Navigli"] }), { idealista_zone_page: false });

    expect(cell("zones", 0).textContent).toContain(en["profiles.review.exact"]);
    const idealista = cell("zones", 1).textContent ?? "";
    expect(idealista).toContain(en["profiles.review.approx"]);
    // and says what the approximation is, which is the half that matters
    expect(idealista).toContain(en["profiles.review.whyZoneFreeText"]);
  });

  it("says which portal drops a filter, and why", () => {
    show(params({ condition: "excellent" }), { idealista_unsupported: ["condition"] });

    expect(cell("condition", 0).textContent).toContain(en["profiles.review.exact"]);
    const idealista = cell("condition", 1).textContent ?? "";
    expect(idealista).toContain(en["profiles.review.dropped"]);
    expect(idealista).toContain(en["profiles.review.whyCondition"]);
  });

  it("reports the drawn area as the one thing Idealista cannot carry at all", () => {
    show(
      params({ drawn_area: { kind: "circle", points: 0, radius_m: 1500, lat: 45.45, lng: 9.17 } }),
      {
        immobiliare: "https://www.immobiliare.it/search-list/?centro=45.45,9.17&raggio=1500",
        idealista_unsupported: ["drawn_area"],
      },
    );

    expect(cell("area", 0).textContent).toContain(en["profiles.review.exact"]);
    expect(cell("area", 1).textContent).toContain(en["profiles.review.whyDrawnArea"]);
  });

  it("does not claim Immobiliare kept an area its rebuilt URL cannot state", () => {
    // the form has no field for a shape, so a URL regenerated from it loses one
    show(params({ drawn_area: { kind: "polygon", points: 24, radius_m: 0, lat: null, lng: null } }));
    expect(cell("area", 0).textContent).toContain(en["profiles.review.dropped"]);
  });
});

describe("the review is offline", () => {
  it("offers the live Idealista check as a press, never as a side effect", () => {
    show(params({ zone: "Navigli", zones: ["Navigli"] }));
    expect(screen.getByText(en["profiles.review.verifyZone"])).toBeTruthy();
  });

  it("says nothing about verification when there is no zone to verify", () => {
    show(params());
    expect(screen.queryByText(en["profiles.review.verifyZone"])).toBeNull();
  });
});
