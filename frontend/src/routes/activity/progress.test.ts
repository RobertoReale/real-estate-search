/** The one rule this screen must not break: no proportion without a total. */

import { describe, expect, it } from "vitest";

import type { ScanProgress } from "../../types";
import { outcomeLabel, pageProportion, phaseLabel, worthExplaining } from "./progress";

function progress(over: Partial<ScanProgress> = {}): ScanProgress {
  return {
    active: true,
    phase: "fetching",
    detail: "",
    profile: "Milano",
    profile_index: 1,
    profile_total: 2,
    portal: "immobiliare",
    page: 3,
    total_pages: null,
    listings: 41,
    total_listings: null,
    transport: "http",
    waiting_seconds: 0,
    ...over,
  };
}

describe("pageProportion", () => {
  it("refuses a fraction where the portal declared no total", () => {
    // The common case, and the reason the whole module exists: Idealista
    // frequently declares nothing, and the caller must fall back to a count.
    expect(pageProportion(progress())).toBeNull();
    expect(pageProportion(progress({ total_pages: 0 }))).toBeNull();
    expect(pageProportion(progress({ total_pages: -1 }))).toBeNull();
    expect(pageProportion(null)).toBeNull();
    expect(pageProportion(undefined)).toBeNull();
  });

  it("gives the fraction where a real total came back", () => {
    expect(pageProportion(progress({ page: 3, total_pages: 8 })))
      .toEqual({ done: 3, total: 8 });
  });

  it("never runs past the total the portal stated", () => {
    // A portal that declares eight pages and serves nine is the same lie in
    // the other direction: a bar drawn past its own end.
    expect(pageProportion(progress({ page: 9, total_pages: 8 })))
      .toEqual({ done: 8, total: 8 });
    expect(pageProportion(progress({ page: -2, total_pages: 8 })))
      .toEqual({ done: 0, total: 8 });
  });
});

describe("phaseLabel", () => {
  it("names the phases the scanner reports", () => {
    expect(phaseLabel("waiting")).toBe("activity.phaseWaiting");
    expect(phaseLabel("fetching")).toBe("activity.phaseFetching");
  });

  it("is vague rather than untranslated about a phase it does not know", () => {
    // A newer backend naming a new phase must reach an older dashboard as
    // imprecise, never as a raw English string in an Italian sentence.
    expect(phaseLabel("quarantining")).toBe("activity.phaseScanning");
    expect(phaseLabel("")).toBe("activity.phaseScanning");
  });
});

describe("outcomeLabel", () => {
  it("keeps the judgement out of the identifying tones", () => {
    expect(outcomeLabel("ok")).toEqual({ label: "activity.outcomeOk", tone: "positive" });
    expect(outcomeLabel("blocked")).toEqual({ label: "activity.outcomeBlocked", tone: "caution" });
    expect(outcomeLabel("error")).toEqual({ label: "activity.outcomeError", tone: "negative" });
    expect(outcomeLabel("no_results"))
      .toEqual({ label: "activity.outcomeNoResults", tone: "neutral" });
  });

  it("does not colour an outcome it cannot read", () => {
    expect(outcomeLabel("something_new"))
      .toEqual({ label: "activity.outcomeUnknown", tone: "neutral" });
  });
});

describe("worthExplaining", () => {
  it("spends the backend's own sentence only on the runs that need it", () => {
    expect(worthExplaining("ok")).toBe(false);
    expect(worthExplaining("blocked")).toBe(true);
    expect(worthExplaining("no_results")).toBe(true);
  });
});
