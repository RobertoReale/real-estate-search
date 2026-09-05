// The accessibility assertion the primitive tests share.
//
// axe-core checks the parts of accessibility a machine can check: that a control
// has a name, that a name is not duplicated, that `aria-*` attributes are real
// ones pointing at elements that exist, that a role's required children are
// present. It cannot check whether the name is the right name, or whether the
// interaction makes sense — which is why every test here pairs it with a
// keyboard walk-through rather than treating a clean axe run as the whole
// answer.
//
// Run against the rendered container, not the page: each test mounts one
// primitive in isolation, so page-level rules (is there an h1, is everything
// inside a landmark) would be reporting on a document the app never renders.
import axe from "axe-core";
import { expect } from "vitest";

const RULES: axe.RuleObject = {
  // Contrast is a property of pixels, and jsdom draws none: it applies no
  // stylesheet, so every element reads as black on transparent and the rule
  // either fires on everything or is skipped as indeterminate. Contrast is
  // settled where it can be measured — `src/styles/tokens.css` pairs each ink
  // with the surface it is legible on, and the browser suite runs axe with this
  // rule on, against the real build.
  "color-contrast": { enabled: false },
  // A primitive is not a page. These four ask whether the *document* is
  // navigable — is there a main landmark, an h1, a skip link, is every region
  // labelled — and the answer for a `<Checkbox>` mounted alone in an empty body
  // is meaningless. They are the right questions to ask of the app, and the
  // browser suite asks them there, against a rendered route.
  region: { enabled: false },
  "landmark-one-main": { enabled: false },
  "page-has-heading-one": { enabled: false },
  bypass: { enabled: false },
};

/** Fails the test with the rule, the reason and the offending markup. */
export async function expectAccessible(container: HTMLElement): Promise<void> {
  const { violations } = await axe.run(container, { resultTypes: ["violations"], rules: RULES });
  expect(violations.flatMap((violation) => violation.nodes.map(
    (node) => `${violation.id}: ${violation.help} — ${node.html}`,
  ))).toEqual([]);
}
