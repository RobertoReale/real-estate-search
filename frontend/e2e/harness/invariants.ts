/** The two rules every screen of every journey has to pass, whatever it is.
 *
 *  A journey asserts what one user does. These assert what has to be true of
 *  *any* screen the app can put in front of anyone, so they are written once and
 *  applied at every stop of every journey rather than remembered per test:
 *
 *    1. **The page never scrolls sideways.** Horizontal overflow is the defect
 *       a phone user meets first and a laptop user never sees, which is exactly
 *       why it survives code review. Checked at three widths — a phone, a
 *       tablet, and the laptop the app is developed on.
 *    2. **No serious or critical accessibility violation.** `axe-core`'s own
 *       severities: "serious" and "critical" are the ones that stop somebody
 *       using the app, while "minor" and "moderate" are advice. Only the first
 *       two are gated, so the check stays a statement about whether the product
 *       works rather than a style opinion.
 *
 *  Both report *what* failed, not just that something did: the overflow check
 *  names the elements sticking out past the viewport and the axe check names the
 *  rule and the nodes. A failure whose message does not say where to look costs
 *  more than the bug.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Phone, tablet, laptop. The three the responsive rules are written against
 *  (see `docs/conventions.md`), and the three A.3 pins the suite to. */
export const WIDTHS = [390, 768, 1440] as const;

/** Tall enough that a screen is judged on its width, not on what a short
 *  viewport pushes below the fold. */
const HEIGHT = 900;

/** axe severities that fail the run. The other two are reported by axe as
 *  advice and would turn every journey into an accessibility backlog. */
const BLOCKING = new Set(["serious", "critical"]);

interface Overflowing {
  readonly tag: string;
  readonly right: number;
  readonly text: string;
}

/** Elements whose right edge lands past the document's own width — the ones
 *  actually causing the sideways scroll, not merely sitting inside it. */
async function overflowingElements(page: Page): Promise<Overflowing[]> {
  return page.evaluate(() => {
    const limit = document.documentElement.clientWidth;
    const over = Array.from(document.querySelectorAll<HTMLElement>("body *")).filter((el) => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && box.right > limit + 1;
    });
    // Only the innermost offenders. An element sticking out pushes every
    // ancestor out with it, and a list headed by <main> buries the one control
    // that is actually too wide.
    return over
      .filter((el) => !over.some((other) => other !== el && el.contains(other)))
      .slice(0, 6)
      .map((el) => ({
        tag:
          el.tagName.toLowerCase() +
          (typeof el.className === "string" && el.className
            ? `.${el.className.split(/\s+/)[0]}`
            : ""),
        right: Math.round(el.getBoundingClientRect().right),
        text: (el.textContent ?? "").trim().slice(0, 60),
      }));
  });
}

/** Checks both rules at all three widths and leaves the page as it was found.
 *
 *  `where` names the screen in the failure message — "the grid", "the property
 *  detail" — because "expected 390 to be >= 542" on its own says nothing about
 *  which of a journey's stops was the broken one.
 *
 *  Soft assertions throughout: a screen that overflows at 390px almost certainly
 *  overflows at 768px too, and stopping at the first would turn one fix into six
 *  runs to find the rest. The test still fails; it fails with the whole list.
 */
export async function checkScreen(page: Page, where: string): Promise<void> {
  const original = page.viewportSize();

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: HEIGHT });
    // One frame for the layout to settle: `setViewportSize` resolves before the
    // browser has re-laid-out, and a measurement taken then is the old one.
    await page.evaluate(
      () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
    );

    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    if (scrollWidth > clientWidth + 1) {
      const culprits = await overflowingElements(page);
      expect.soft(
        scrollWidth,
        [
          `${where} scrolls sideways at ${width}px: the document is ${scrollWidth}px `,
          `wide in a ${clientWidth}px viewport.`,
          ...culprits.map((c) => `\n  ${c.tag} reaches ${c.right}px — "${c.text}"`),
        ].join(""),
      ).toBeLessThanOrEqual(clientWidth + 1);
    }

    const results = await new AxeBuilder({ page }).analyze();
    const blocking = results.violations.filter((v) => BLOCKING.has(v.impact ?? ""));
    expect.soft(
      blocking.map((v) => `${v.impact} · ${v.id}: ${v.help}`),
      [
        `${where} has ${blocking.length} serious or critical accessibility `,
        `violation(s) at ${width}px:`,
        ...blocking.flatMap((v) => [
          `\n  ${v.id} (${v.impact}) — ${v.help}`,
          ...v.nodes.slice(0, 3).map((n) => `\n    ${n.target.join(" ")}`),
        ]),
      ].join(""),
    ).toEqual([]);
  }

  if (original) await page.setViewportSize(original);
}
