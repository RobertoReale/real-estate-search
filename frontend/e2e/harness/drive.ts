/** Operating a control by its inventory id, and proving it took.
 *
 *  `coverage.spec.ts` drives two hundred-odd controls. Written out one at a
 *  time, the assertion that a field holds what was typed would be four lines
 *  each and the interesting ones would be lost in them. These say the same
 *  thing in one: type here, and the field holds it; tick this, and it is
 *  ticked; choose that, and it is chosen.
 *
 *  A control is addressed by what the inventory calls it and never by a CSS
 *  class or a label — the labels are translated and Phase C rewrites the
 *  classes, while `data-action` is the one name that is *declared* to be
 *  stable. `.first()` throughout: a control rendered per row (a portal
 *  checkbox, a backup's Download) is one control the user meets several times,
 *  and the inventory has one row for it.
 */
import { expect, type Locator, type Page } from "@playwright/test";
import type { ActionId } from "../actions";

export type Scope = Page | Locator;

/** The control with this id, inside `scope`. */
export function control(scope: Scope, id: ActionId): Locator {
  return scope.locator(`[data-action="${id}"]`).first();
}

/** Types into a text, number or textarea control and proves it holds the value. */
export async function fill(scope: Scope, id: ActionId, value: string): Promise<void> {
  const el = control(scope, id);
  await el.fill(value);
  await expect(el, `${id} did not take what was typed into it`).toHaveValue(value);
}

/** Flips a checkbox and proves it flipped. Returns the state it left it in.
 *
 *  A click and then the expectation, for the same reason as `setTicked`: some
 *  of these boxes are answered by the backend rather than by the click, and
 *  `setChecked` reads the state back in the same tick. */
export async function toggle(scope: Scope, id: ActionId): Promise<boolean> {
  const el = control(scope, id);
  const before = await el.isChecked();
  await el.click();
  await expect(el, `${id} did not change state`).toBeChecked({ checked: !before });
  return !before;
}

/** Sets a checkbox to a known state, whatever it was in.
 *
 *  A click and then the expectation, rather than `setChecked`: several of these
 *  boxes are not controlled by the click alone — "select all" asks the backend
 *  for the whole filtered set first — and `setChecked` verifies the state in the
 *  same tick, which fails on a box that is right a moment later. */
export async function setTicked(scope: Scope, id: ActionId, on: boolean): Promise<void> {
  const el = control(scope, id);
  if (await el.isChecked() !== on) await el.click();
  await expect(el, `${id} did not reach the state it was set to`).toBeChecked({ checked: on });
}

/** Picks an option and proves the select carries it. */
export async function choose(scope: Scope, id: ActionId, value: string): Promise<void> {
  const el = control(scope, id);
  await el.selectOption(value);
  await expect(el, `${id} did not keep the option chosen`).toHaveValue(value);
}

/** Picks an option by its visible text, for a select whose values are ids. */
export async function chooseLabel(scope: Scope, id: ActionId, label: string | RegExp): Promise<void> {
  await control(scope, id).selectOption({ label: label as string });
}

/** Presses a button, link or any other clickable control. */
export async function press(scope: Scope, id: ActionId, opts?: Parameters<Locator["click"]>[0]): Promise<void> {
  await control(scope, id).click(opts);
}

/**
 * Walks the tab order from a point on the page and reports what it reached.
 *
 * This is the keyboard axis, and it is deliberately real Tab presses rather than
 * `element.focus()`: focusing from a script succeeds on things a keyboard can
 * never get to — a `div` with an `onClick` and no `tabindex`, a control inside
 * an `aria-hidden` container — which would turn the check into a restatement of
 * "the element exists".
 *
 * `anchor` is where the walk begins, and it has to be said out loud rather than
 * assumed. Tab moves *forward* from wherever focus already is, and this app puts
 * its dialogs at the end of the document, after sixty cards; started from the
 * top of the page, a walk to the property modal would be three hundred presses
 * of nothing. So the caller names a non-focusable element on the surface under
 * test — a heading, a panel — and clicking it sets the sequential focus
 * navigation starting point there. What is then proved is what the assertion
 * claims and no more: from that point, Tab alone reaches every control.
 */
export async function tabOrder(
  page: Page,
  expected: readonly ActionId[],
  anchor: Locator,
  limit = 400,
): Promise<Set<string>> {
  const wanted = new Set<string>(expected);
  const reached = new Set<string>();
  // Clicking a non-focusable element is what moves the starting point; blurring
  // does not, and Chromium then resumes from wherever the last control was —
  // which is how a walk for the filter bar can start below it and never come
  // back round.
  await anchor.click({ position: { x: 1, y: 1 } });

  for (let i = 0; i < limit && reached.size < wanted.size; i++) {
    await page.keyboard.press("Tab");
    const id = await page.evaluate(
      () => document.activeElement?.closest<HTMLElement>("[data-action]")?.dataset.action ?? null,
    );
    if (id && wanted.has(id)) reached.add(id);
  }
  return reached;
}

/** Asserts every one of `expected` is reachable by pressing Tab alone from
 *  `anchor`, which defaults to the top of the page. */
export async function reachableByKeyboard(
  page: Page,
  where: string,
  expected: readonly ActionId[],
  anchor?: Locator,
): Promise<void> {
  const reached = await tabOrder(page, expected, anchor ?? page.locator("h1").first());
  const missed = expected.filter((id) => !reached.has(id));
  expect(
    missed,
    `${where}: ${missed.length} control(s) cannot be reached with the Tab key alone. `
    + "A control a pointer can operate and a keyboard cannot is one half the users "
    + "cannot use at all.",
  ).toEqual([]);
}

/**
 * Every inventoried control currently on screen, enabled, and safe to press.
 *
 * Used by the backend-failure sweep, which fires whatever it finds: the
 * exclusions are the ones that would end the run rather than test it — a page
 * reload takes the sweep's own page away, and a `window.confirm` left unanswered
 * blocks it.
 */
export async function visibleActions(page: Page, except: readonly ActionId[] = []): Promise<string[]> {
  const skip = new Set<string>(except);
  const ids = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>("[data-action]"))
      .filter((el) => {
        const box = el.getBoundingClientRect();
        return box.width > 0 && box.height > 0 && !(el as HTMLInputElement).disabled;
      })
      .map((el) => el.dataset.action ?? ""),
  );
  return [...new Set(ids)].filter((id) => id && !skip.has(id));
}
