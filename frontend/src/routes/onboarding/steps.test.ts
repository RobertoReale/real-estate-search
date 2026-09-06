import { beforeEach, describe, expect, it } from "vitest";

import {
  clampStep, dismissGuide, furthestStep, guideDismissed, shouldGuide, stepAfter,
  stepBefore, STEPS,
} from "./steps";

beforeEach(() => localStorage.clear());

describe("the order", () => {
  it("runs from what the app is to the first scan", () => {
    expect(STEPS).toEqual(["what", "search", "scan"]);
  });

  it("saturates at both ends", () => {
    expect(stepAfter("scan")).toBe("scan");
    expect(stepBefore("what")).toBeNull();
    expect(stepAfter(stepBefore("search")!)).toBe("search");
  });
});

describe("what a step needs before it means anything", () => {
  it("stops short of the scan until a search exists", () => {
    expect(furthestStep(false)).toBe("search");
    expect(clampStep("scan", false)).toBe("search");
  });

  it("opens the scan the moment one does", () => {
    expect(furthestStep(true)).toBe("scan");
    expect(clampStep("scan", true)).toBe("scan");
  });

  it("never pushes anyone forward", () => {
    expect(clampStep("what", true)).toBe("what");
    expect(clampStep("search", true)).toBe("search");
  });
});

describe("the bare address", () => {
  it("opens the guide when there is nothing else to show", () => {
    expect(shouldGuide(false)).toBe(true);
  });

  it("does not, once a search exists", () => {
    expect(shouldGuide(true)).toBe(false);
  });

  it("does not, once the guide has been left", () => {
    expect(guideDismissed()).toBe(false);
    dismissGuide();
    expect(guideDismissed()).toBe(true);
    expect(shouldGuide(false)).toBe(false);
  });
});
