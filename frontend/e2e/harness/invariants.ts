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
 *  names the elements sticking out past the viewport, and the axe check names
 *  the rule, the nodes, the measurement axe took and the style the browser had
 *  resolved at that instant. A failure whose message does not say where to look
 *  costs more than the bug — a bare "color-contrast (serious)" once sent a
 *  session after a design token that measured 5.2:1 and was never at fault.
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

type AxeResults = Awaited<ReturnType<AxeBuilder["analyze"]>>;
type ViolationNode = AxeResults["violations"][number]["nodes"][number];

/** What `color-contrast` records under each node's checks: the two colours it
 *  resolved, the ratio it got, and the ratio it wanted. */
interface ContrastData {
  readonly fgColor?: string;
  readonly bgColor?: string;
  readonly contrastRatio?: number;
  readonly expectedContrastRatio?: string;
  readonly bgOverlap?: number;
}

/** axe's own measurement for a node, when it took one.
 *
 *  A contrast failure that names the rule and not the numbers cannot be acted
 *  on: "elements must meet minimum contrast" is equally true of every button in
 *  the app, and the only question worth asking is which pair of colours *this*
 *  one resolved to at the instant of the check. Without it the reader is left
 *  reasoning from the stylesheet, which is exactly how a token gets blamed for
 *  an overlay. */
function measuredContrast(node: ViolationNode): string | null {
  for (const check of [...node.any, ...node.all, ...node.none]) {
    const data = check.data as ContrastData | null | undefined;
    if (!data || typeof data !== "object" || data.contrastRatio === undefined) continue;
    const parts = [
      `fg ${data.fgColor}`,
      `bg ${data.bgColor}`,
      `ratio ${data.contrastRatio}`,
      `needs ${data.expectedContrastRatio}`,
    ];
    // Non-zero bgOverlap means axe found something covering the element, so the
    // bg above is a blend rather than the token the stylesheet names.
    if (data.bgOverlap !== undefined) parts.push(`bgOverlap ${data.bgOverlap}`);
    return parts.join(", ");
  }
  return null;
}

/** The browser's own resolved values for the offending node, read at the moment
 *  the check failed. Read alongside `measuredContrast`, this is what separates
 *  "the colours really are those two" from "it was measured mid-transition, or
 *  through an opacity, or against a background that is not what it looks like". */
async function computedStyleOf(page: Page, selector: string): Promise<string> {
  return page.evaluate((sel) => {
    let el: Element | null = null;
    try {
      el = document.querySelector(sel);
    } catch {
      return `unreadable selector`;
    }
    if (!el) return "no longer in the document";
    const style = getComputedStyle(el);
    return [
      `color ${style.color}`,
      `background-color ${style.backgroundColor}`,
      `opacity ${style.opacity}`,
    ].join(", ");
  }, selector);
}

/** `target` is a selector, or a frame path ending in one. */
function selectorOf(node: ViolationNode): string {
  return node.target.map((part) => (Array.isArray(part) ? part.join(" ") : part)).join(" ");
}

/** Longest a screen is given to stop moving. A transition in this app is
 *  measured in milliseconds; this is only here so a bug cannot hang the suite. */
const SETTLE_TIMEOUT = 2000;

/** Waits until the screen has stopped changing colour — layout re-laid-out *and*
 *  every running transition finished.
 *
 *  Two frames of `requestAnimationFrame` is enough for layout and not enough for
 *  a transition, and the difference is a real failure this suite produced: the
 *  onboarding button that becomes the solid accent one keeps its DOM node when
 *  React swaps its classes, so the class change starts a `background-color` and
 *  `color` transition. Measured inside it, Chromium reports the interpolated
 *  `oklab(...)` midpoint rather than either end, and axe scored a passing
 *  5.11:1 button at 2.75:1. It failed or passed on machine load alone.
 *
 *  So the wait is on the browser's own signal. `getAnimations()` returns CSS
 *  transitions along with everything else, and each one's `finished` resolves
 *  when it is genuinely over — no frame count can stand in for that. Animations
 *  that repeat forever (a spinner, a pulsing skeleton) are skipped, because
 *  waiting for one to finish would mean waiting for ever. */
async function settle(page: Page): Promise<void> {
  await page.evaluate(async (timeout) => {
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
    const running = document
      .getAnimations()
      .filter((animation) => animation.effect?.getTiming().iterations !== Infinity);
    // `finished` rejects on a cancelled animation, which is a settled screen too.
    const done = Promise.all(running.map((animation) => animation.finished.catch(() => undefined)));
    await Promise.race([done, new Promise((resolve) => setTimeout(resolve, timeout))]);
  }, SETTLE_TIMEOUT);
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
    // `setViewportSize` resolves before the browser has re-laid-out, and nothing
    // measured here — width or colour — means anything until the screen is still.
    await settle(page);

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
    if (blocking.length > 0) {
      // Built only on failure: it reads the page again per node, and on a green
      // run there is nothing to describe.
      const detail: string[] = [];
      for (const violation of blocking) {
        detail.push(`\n  ${violation.id} (${violation.impact}) — ${violation.help}`);
        for (const node of violation.nodes.slice(0, 3)) {
          const selector = selectorOf(node);
          detail.push(`\n    ${selector}`);
          const measured = measuredContrast(node);
          if (measured) detail.push(`\n      axe measured: ${measured}`);
          detail.push(`\n      computed now: ${await computedStyleOf(page, selector)}`);
        }
      }
      expect.soft(
        blocking.map((v) => `${v.impact} · ${v.id}: ${v.help}`),
        [
          `${where} has ${blocking.length} serious or critical accessibility `,
          `violation(s) at ${width}px:`,
          ...detail,
        ].join(""),
      ).toEqual([]);
    }
  }

  if (original) await page.setViewportSize(original);
}
