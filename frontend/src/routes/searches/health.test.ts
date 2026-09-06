/** The precedence between the states, which is the whole of `health.ts`. */

import { describe, expect, it } from "vitest";

import { needsAttention, profileHealth, type HealthInput } from "./health";

function profile(over: Partial<HealthInput> = {}): HealthInput {
  return {
    is_active: true,
    last_run_status: "ok",
    consecutive_failures: 0,
    last_run_detail: "",
    ...over,
  };
}

describe("profileHealth", () => {
  it("reads a running search from its last run", () => {
    expect(profileHealth(profile()).state).toBe("working");
    expect(profileHealth(profile({ last_run_status: "no_results" })).state).toBe("quiet");
    expect(profileHealth(profile({ last_run_status: "blocked" })).state).toBe("blocked");
    expect(profileHealth(profile({ last_run_status: "error" })).state).toBe("failing");
  });

  it("calls a search that has never run neither working nor broken", () => {
    expect(profileHealth(profile({ last_run_status: "" })).state).toBe("unrun");
    // A status this frontend has never heard of is the same case: the honest
    // answer is that nothing is known, not a guess in either direction.
    expect(profileHealth(profile({ last_run_status: "quarantined" })).state).toBe("unrun");
  });

  it("lets paused win over whatever the last run said", () => {
    // The regression this exists for: a search switched off eleven days ago
    // still showed "OK", because "OK" was its last run's word and the badge
    // never looked at whether the search was still on.
    expect(profileHealth(profile({ is_active: false })).state).toBe("paused");
    expect(
      profileHealth(profile({ is_active: false, last_run_status: "error" })).state,
    ).toBe("paused");
  });

  it("carries the streak and the run's own words", () => {
    const h = profileHealth(profile({
      last_run_status: "blocked", consecutive_failures: 4,
      last_run_detail: "the portal answered 403",
    }));
    expect(h.streak).toBe(4);
    expect(h.detail).toBe("the portal answered 403");
  });

  it("never reports a negative streak or an undefined detail", () => {
    const h = profileHealth({
      is_active: true, last_run_status: "ok",
      consecutive_failures: -1, last_run_detail: "",
    });
    expect(h.streak).toBe(0);
    expect(h.detail).toBe("");
  });
});

describe("needsAttention", () => {
  it("is true only for the two states the user has to act on", () => {
    expect(needsAttention("failing")).toBe(true);
    expect(needsAttention("blocked")).toBe(true);
    // A search that found nothing is the market's answer, and a paused one is
    // the user's own decision. Colouring either as a problem is how a screen
    // teaches its reader to stop reading colours.
    expect(needsAttention("quiet")).toBe(false);
    expect(needsAttention("paused")).toBe(false);
    expect(needsAttention("working")).toBe(false);
    expect(needsAttention("unrun")).toBe(false);
  });
});
