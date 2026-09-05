import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

/** The rule this file exists to enforce: a component names a *role*, never a
 *  colour. `bg-surface`, not `bg-white dark:bg-slate-900`; `text-negative-ink`,
 *  not `text-rose-600`.
 *
 *  It is a rule and not a convention because the failure mode is silent and
 *  cumulative. Six near-identical buttons in the batch bar differed by accident
 *  rather than by intent, and nothing in the build could tell the difference
 *  between the variant somebody meant and the one they typed from memory. Once
 *  every colour resolves through `tokens.css`, re-hueing the whole product is
 *  one file — and until this test exists, one hand-typed `bg-blue-600` is all it
 *  takes to make that untrue again.
 *
 *  It also catches the escape hatch: an arbitrary value (`bg-[#2563eb]`) is a
 *  raw colour wearing brackets. */

// Not derived from `import.meta.url`: under the jsdom environment that is an
// http:// URL, not a file one. Vitest's cwd is the frontend project root.
const SRC = resolve(process.cwd(), "src");

const PROPERTIES =
  "bg|text|border|ring|divide|outline|fill|stroke|shadow|decoration|placeholder|caret|accent|from|via|to";

const RAMPS = [
  "slate", "gray", "zinc", "neutral", "stone",
  "red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal",
  "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose",
].join("|");

/** `bg-blue-600`, `dark:text-slate-500`, `hover:border-rose-500/30`. The shade
 *  number is what makes this precise: the token roles borrow two of Tailwind's
 *  ramp names (`neutral`, `accent`), and `bg-neutral-soft` is the thing this
 *  rule is asking for, not the thing it forbids. */
const RAMP_UTILITY = new RegExp(`\\b(?:${PROPERTIES})-(?:${RAMPS})-(?:50|\\d{3})\\b`, "g");

/** `text-white`, `bg-black/60`. */
const ABSOLUTE_UTILITY = new RegExp(`\\b(?:${PROPERTIES})-(?:white|black)\\b`, "g");

/** `bg-[#2563eb]`, `text-[rgb(37,99,235)]`, `border-[oklch(0.5_0.2_260)]`. */
const ARBITRARY_COLOR = new RegExp(
  `\\b(?:${PROPERTIES})-\\[(?:#|rgb|rgba|hsl|hsla|oklch|oklab|lab|lch|color-mix)[^\\]]*\\]`,
  "gi",
);

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...sources(path));
    } else if (/\.tsx?$/.test(entry.name) && !/\.(test|spec)\.tsx?$/.test(entry.name)) {
      out.push(path);
    }
  }
  return out;
}

describe("no component names a colour", () => {
  const files = sources(SRC);

  it("scans the source tree", () => {
    // a rule that silently scans nothing passes forever
    expect(files.length).toBeGreaterThan(40);
  });

  it("finds only roles, never raw colour utilities", () => {
    // every offender at once: fixing these one test run at a time is what makes
    // a rule like this feel like an obstacle instead of a map
    const offenders = files.flatMap((path) => {
      const text = readFileSync(path, "utf8");
      const found = new Set([
        ...(text.match(RAMP_UTILITY) ?? []),
        ...(text.match(ABSOLUTE_UTILITY) ?? []),
        ...(text.match(ARBITRARY_COLOR) ?? []),
      ]);
      return found.size
        ? [`${relative(SRC, path)}: ${[...found].sort().join(", ")}`]
        : [];
    });

    expect(
      offenders,
      "Use a role from src/styles/tokens.css instead. The roles are what carry the " +
        "light and dark values, so a raw colour utility is also a component that only " +
        "looks right in one theme.",
    ).toEqual([]);
  });
});
