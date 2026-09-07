import { describe, expect, it } from "vitest";
import { it as itDict } from "../i18n/it";
import { translate } from "../i18n";
import { humanizeFloor } from "./format";

// No provider is mounted here, so these render in the default language. Assert
// against the dictionary rather than a literal: the words belong to the copy,
// the mapping is what this test is about.
describe("humanizeFloor", () => {
  it("maps the cryptic Italian portal codes to words", () => {
    // "floor R" meant nothing to a user; these are the codes Immobiliare stores
    expect(humanizeFloor("R")).toBe(itDict["floor.raised"]);
    expect(humanizeFloor("r")).toBe(itDict["floor.raised"]);
    expect(humanizeFloor("T")).toBe(itDict["floor.ground"]);
    expect(humanizeFloor("PT")).toBe(itDict["floor.ground"]);
    expect(humanizeFloor("S")).toBe(itDict["floor.basement"]);
  });

  it("prefixes a bare number so it reads as a floor", () => {
    expect(humanizeFloor("6")).toBe(translate("it", "floor.numbered", { floor: "6" }));
    expect(humanizeFloor("-1")).toBe(translate("it", "floor.numbered", { floor: "-1" }));
  });

  it("passes through already-spelled-out or unexpected labels unchanged", () => {
    // never hide information: an odd value shows as-is, not blanked
    expect(humanizeFloor("attico")).toBe("attico");
    expect(humanizeFloor("R 6")).toBe("R 6");
    expect(humanizeFloor("")).toBe("");
  });
});
