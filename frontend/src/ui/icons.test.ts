/**
 * The interface is drawn, not typed.
 *
 * Emoji were the icon set until this test existed, and the reason they had to
 * go is in the header of `icons.tsx`. The reason a *test* had to exist is
 * different: an emoji is one keystroke, it renders as something in every
 * editor, and nothing about it looks wrong in a diff — so a single hurried
 * label is all it takes for two icon systems to be in the app again, and the
 * second one is invisible until somebody opens the app on the operating system
 * that draws it badly.
 *
 * So this reads the source rather than the rendered output. The rule is about
 * what is written down: no pictographic character anywhere the user can see it,
 * whether it reaches the screen through JSX or through the dictionaries. The
 * dictionaries are the point — a cog typed into the front of the word
 * "Settings" is chrome that a test scanning only components would never find,
 * and that is exactly where they all were.
 *
 * `\p{Extended_Pictographic}` is the predicate rather than a hand-written list
 * of ranges: it is the Unicode property that means "this is a pictograph",
 * which is the question being asked. It deliberately does not match the
 * punctuation that belongs in prose — em dashes, ellipses, `≥`, `·`, `€` — so
 * this never argues with a sentence. Alongside it sits a short list of
 * characters that are not pictographs but were being used as drawings anyway:
 * a tick, a cross, a chevron, a pentagon.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Where the user-facing source lives. `src/i18n` is in the list because a
 *  label is interface wherever it is stored. */
const ROOTS = ["src/components", "src/ui", "src/routes", "src/i18n", "src/App.tsx"];

/** This file. It has to name the characters it forbids, so it cannot obey
 *  itself — and an exception list of one is cheaper than the alternative,
 *  which is spelling every one of them as an escape and making the rule
 *  unreadable in the file that defines it. */
const SELF = "icons.test.ts";

/** A pictograph, plus the text characters this codebase used as icons. */
const CHROME = /\p{Extended_Pictographic}|[✓✗☆★✕⬠▼▲●↗]/u;

/** The one exception, and it is not chrome: OpenStreetMap's licence requires
 *  its attribution to be shown, and `©` happens to be a pictograph. */
const ALLOWED = /©/gu;

function sources(path: string): string[] {
  if (statSync(path).isFile()) return [path];
  return readdirSync(path).flatMap((name) => {
    const child = join(path, name);
    if (statSync(child).isDirectory()) return sources(child);
    if (name === SELF) return [];
    return /\.(ts|tsx|css)$/.test(name) ? [child] : [];
  });
}

describe("the interface carries no emoji", () => {
  const files = ROOTS.flatMap((root) => sources(root));

  it("finds source to check", () => {
    expect(files.length).toBeGreaterThan(50);
  });

  for (const file of files) {
    it(`${file.replace(/\\/g, "/")} draws its icons`, () => {
      const offenders = readFileSync(file, "utf8")
        .replace(ALLOWED, "")
        .split("\n")
        .map((line, i) => [i + 1, line] as const)
        .filter(([, line]) => CHROME.test(line))
        .map(([n, line]) => `${n}: ${line.trim()}`);
      // The message is the fix: the barrel is where the replacement lives.
      expect(offenders, "use an icon from src/ui/icons.tsx instead").toEqual([]);
    });
  }
});
