import { createElement } from "react";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { en } from "./en";
import { it as itDict } from "./it";
import { interpolate, resolveInitialLang, translate, useT } from "./index";
import { humanizeFloor } from "../utils/format";

describe("dictionaries", () => {
  // `it: Dict` already makes a missing key a compile error, but a stale build
  // artifact would not: this fails loudly at test time too.
  it("cover exactly the same keys in both languages", () => {
    expect(Object.keys(itDict).sort()).toEqual(Object.keys(en).sort());
  });

  it("keep the same placeholders on both sides of a key", () => {
    // A dropped `{count}` renders a sentence with a hole in it — invisible in
    // review, obvious to the user, and only in one language.
    const placeholders = (s: string) =>
      (s.match(/\{(\w+)\}/g) ?? []).sort().join(",");
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(
        placeholders(itDict[key]),
        `placeholders differ for "${key}"`,
      ).toBe(placeholders(en[key]));
    }
  });

  it("never leaves a translation empty", () => {
    for (const [key, value] of Object.entries(itDict)) {
      expect(value.trim(), `empty Italian value for "${key}"`).not.toBe("");
    }
  });
});

describe("interpolate", () => {
  it("substitutes named placeholders", () => {
    expect(interpolate("{a} and {b}", { a: "x", b: 2 })).toBe("x and 2");
  });

  it("leaves an unknown placeholder in place rather than blanking it", () => {
    // a visible `{oops}` is a bug report; a silent gap is a mystery
    expect(interpolate("hi {oops}", { a: 1 })).toBe("hi {oops}");
  });

  it("returns the template untouched with no params", () => {
    expect(interpolate("plain")).toBe("plain");
  });
});

describe("translate", () => {
  it("renders the requested language", () => {
    expect(translate("en", "common.save")).toBe("Save");
    expect(translate("it", "common.save")).toBe("Salva");
  });

  it("fills placeholders from params", () => {
    expect(translate("en", "filters.countProperties", { count: 3 })).toBe("3 properties");
    expect(translate("it", "filters.countProperties", { count: 3 })).toBe("3 immobili");
  });
});

describe("resolveInitialLang", () => {
  it("opens in Italian when nothing has been chosen", () => {
    // The browser is not consulted at all. It used to be, which made an Italian
    // product open in English on any machine whose OS shipped in English.
    expect(resolveInitialLang(null)).toBe("it");
  });

  it("still honours a stored choice, so the switcher is not a formality", () => {
    expect(resolveInitialLang("en")).toBe("en");
    expect(resolveInitialLang("it")).toBe("it");
  });

  it("defaults to Italian for an unsupported or corrupted value", () => {
    // a garbage localStorage value must never leave the UI without a dictionary
    expect(resolveInitialLang("klingon")).toBe("it");
  });
});

describe("outside the provider", () => {
  /** Reads the hook the way every component does, and nothing else. */
  function Probe() {
    return createElement("span", null, useT()("common.save"));
  }

  it("renders Italian rather than falling out of the product's language", () => {
    // No I18nProvider above it: an error boundary that caught the shell, or a
    // component mounted bare. Both halves of the fallback are checked — the
    // hook, and the module-level locale the plain formatters read.
    const { container } = render(createElement(Probe));
    expect(container.textContent).toBe(itDict["common.save"]);
    expect(humanizeFloor("R")).toBe(itDict["floor.raised"]);
  });
});
