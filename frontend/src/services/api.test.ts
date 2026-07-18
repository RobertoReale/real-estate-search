import { describe, expect, it } from "vitest";
import type { PropertyFilters } from "../types";
import { propertyParams } from "./api";

// The first frontend test (the backend has ~500, the UI had zero). It targets
// the propertyParams codec: the one piece of api.ts pure enough to test in
// isolation, and the riskiest to change silently — a filter that stops being
// serialized just quietly drops out of the grid fetch and the dossier export,
// with nothing failing until a human notices missing results.

const base: PropertyFilters = {
  status: "active",
  contract: "sale",
  city: "",
  zone: "",
  q: "",
  source: "",
  profile_id: "",
  tag: "",
  min_price: "",
  max_price: "",
  min_sqm: "",
  max_sqm: "",
  floor_band: "",
  rooms: "",
  portal: "",
  agency: "",
  deal: "",
  min_sqm_price: "",
  max_sqm_price: "",
  merged_only: false,
  only_price_drops: false,
  only_favorites: false,
  sort: "recent",
};

describe("propertyParams", () => {
  it("always emits the three unconditional params", () => {
    const p = propertyParams(base);
    expect(p.get("status")).toBe("active");
    expect(p.get("contract")).toBe("sale");
    expect(p.get("sort")).toBe("recent");
  });

  it("omits empty-string optional filters entirely", () => {
    const p = propertyParams(base);
    for (const key of ["city", "zone", "q", "source", "min_price", "agency", "deal"]) {
      expect(p.has(key)).toBe(false);
    }
  });

  it("serializes every populated string filter", () => {
    const p = propertyParams({
      ...base,
      city: "Milano",
      zone: "Navigli",
      q: "attico",
      source: "email",
      profile_id: "7",
      tag: "visitare",
      min_price: "100000",
      max_price: "300000",
      min_sqm: "50",
      max_sqm: "120",
      floor_band: "high",
      rooms: "3",
      portal: "idealista",
      agency: "Gabetti",
      deal: "undervalued",
      min_sqm_price: "2000",
      max_sqm_price: "4000",
    });
    expect(p.get("city")).toBe("Milano");
    expect(p.get("zone")).toBe("Navigli");
    expect(p.get("q")).toBe("attico");
    expect(p.get("source")).toBe("email");
    expect(p.get("profile_id")).toBe("7");
    expect(p.get("tag")).toBe("visitare");
    expect(p.get("min_price")).toBe("100000");
    expect(p.get("max_price")).toBe("300000");
    expect(p.get("min_sqm")).toBe("50");
    expect(p.get("max_sqm")).toBe("120");
    expect(p.get("floor_band")).toBe("high");
    expect(p.get("rooms")).toBe("3");
    expect(p.get("portal")).toBe("idealista");
    expect(p.get("agency")).toBe("Gabetti");
    expect(p.get("deal")).toBe("undervalued");
    expect(p.get("min_sqm_price")).toBe("2000");
    expect(p.get("max_sqm_price")).toBe("4000");
  });

  it("emits boolean flags only when true, as the string 'true'", () => {
    expect(propertyParams(base).has("merged_only")).toBe(false);
    const p = propertyParams({
      ...base,
      merged_only: true,
      only_price_drops: true,
      only_favorites: true,
    });
    expect(p.get("merged_only")).toBe("true");
    expect(p.get("only_price_drops")).toBe("true");
    expect(p.get("only_favorites")).toBe("true");
  });
});
