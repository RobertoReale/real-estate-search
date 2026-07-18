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
  geo_mode: "",
  center_lat: "",
  center_lng: "",
  radius_m: "",
  poly: "",
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

  it("serializes a radius geo filter only when mode + all three fields are set", () => {
    // mode alone, without coordinates, must not leak a half-built filter
    expect(propertyParams({ ...base, geo_mode: "radius" }).has("center_lat")).toBe(false);
    const p = propertyParams({
      ...base,
      geo_mode: "radius",
      center_lat: "45.46",
      center_lng: "9.19",
      radius_m: "1500",
    });
    expect(p.get("center_lat")).toBe("45.46");
    expect(p.get("center_lng")).toBe("9.19");
    expect(p.get("radius_m")).toBe("1500");
    expect(p.has("poly")).toBe(false);
  });

  it("serializes a polygon geo filter, and radius/polygon are mutually exclusive", () => {
    const p = propertyParams({ ...base, geo_mode: "polygon", poly: "45.1,9.1;45.2,9.2;45.3,9.1" });
    expect(p.get("poly")).toBe("45.1,9.1;45.2,9.2;45.3,9.1");
    expect(p.has("center_lat")).toBe(false);
    // a stale radius left in state must not ride along in polygon mode
    const q = propertyParams({
      ...base,
      geo_mode: "polygon",
      poly: "45.1,9.1;45.2,9.2;45.3,9.1",
      center_lat: "45.46",
      center_lng: "9.19",
      radius_m: "1500",
    });
    expect(q.has("center_lat")).toBe(false);
    expect(q.get("poly")).toBe("45.1,9.1;45.2,9.2;45.3,9.1");
  });

  it("emits no geo params when mode is empty even if stale values remain", () => {
    const p = propertyParams({
      ...base,
      center_lat: "45.46",
      center_lng: "9.19",
      radius_m: "1500",
      poly: "45.1,9.1;45.2,9.2;45.3,9.1",
    });
    for (const key of ["center_lat", "center_lng", "radius_m", "poly"]) {
      expect(p.has(key)).toBe(false);
    }
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
