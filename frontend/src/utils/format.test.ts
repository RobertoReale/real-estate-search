import { describe, expect, it } from "vitest";
import { humanizeFloor } from "./format";

describe("humanizeFloor", () => {
  it("maps the cryptic Italian portal codes to words", () => {
    // "floor R" meant nothing to a user; these are the codes Immobiliare stores
    expect(humanizeFloor("R")).toBe("raised ground floor");
    expect(humanizeFloor("r")).toBe("raised ground floor");
    expect(humanizeFloor("T")).toBe("ground floor");
    expect(humanizeFloor("PT")).toBe("ground floor");
    expect(humanizeFloor("S")).toBe("basement");
  });

  it("prefixes a bare number so it reads as a floor", () => {
    expect(humanizeFloor("6")).toBe("floor 6");
    expect(humanizeFloor("-1")).toBe("floor -1");
  });

  it("passes through already-spelled-out or unexpected labels unchanged", () => {
    // never hide information: an odd value shows as-is, not blanked
    expect(humanizeFloor("attico")).toBe("attico");
    expect(humanizeFloor("R 6")).toBe("R 6");
    expect(humanizeFloor("")).toBe("");
  });
});
