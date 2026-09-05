/**
 * The vocabulary every primitive shares.
 *
 * C.1 decided what a colour *means* — `--negative-ink` rather than `--rose-600`.
 * This is the next question down: which of those meanings a control is allowed
 * to take, and what each one looks like at each level of emphasis. Kept in one
 * module because the alternative is what the batch bar already demonstrated —
 * six buttons whose tones differed by accident, because each was typed from
 * memory next to the one before it.
 *
 * Two axes, and they are independent on purpose:
 *
 * - **tone** is what the control is about. `negative` on a button that hides a
 *   listing is the same statement as `negative` on the chip that says a price
 *   went up; both read the ramp `--negative-*`, and both change together when
 *   the ramp does.
 * - **variant** is how loudly it says it. A screen with three outline buttons
 *   and one solid one has an answer to "what did you want me to do here?"; a
 *   screen with four solid ones does not.
 */

/** The tones a control can take. `info`, `tag` and `rent` are missing here and
 *  present on `Chip`: they identify a thing rather than judge it, and nothing a
 *  user *presses* is identified by a portal or a contract type. */
export type Tone = "accent" | "neutral" | "positive" | "caution" | "negative";

/** How much of the tone the control shows. */
export type Variant = "solid" | "outline" | "ghost";

/**
 * Solid is `accent` and `negative`, and no others — this is a design decision
 * rather than an omission.
 *
 * A filled button is an assertion, and this product makes exactly two of them:
 * *do the thing* and *undo or destroy it*. A filled `caution` green-lights
 * nothing; it is a colour looking for a job. The narrower reason is contrast,
 * and it is measurable: `--on-solid` is white, and of the five ramps only azure
 * and garnet have a step dark enough to carry white text at 4.5:1 *and* a
 * designed hover a shade darker again. Sage-700 clears the text and has nowhere
 * to go on hover; ochre-700 does not clear the text at all. A variant that can
 * only be drawn wrong is better absent than documented.
 */
export type SolidTone = Extract<Tone, "accent" | "negative">;

export const SOLID: Record<SolidTone, string> = {
  accent: "bg-accent hover:bg-accent-hover active:bg-accent-active text-on-solid shadow-accent",
  negative: "bg-negative hover:bg-negative-hover active:bg-negative-deep text-on-solid",
};

/** A bordered control on its own ground. The default, and what most of the app
 *  is: an action offered rather than urged. */
export const OUTLINE: Record<Tone, string> = {
  neutral: "bg-surface hover:bg-sunken border border-line-strong text-ink-body",
  accent: "bg-surface hover:bg-accent-soft border border-accent-line text-accent-ink",
  positive: "bg-surface hover:bg-positive-soft border border-positive-line text-positive-ink",
  caution: "bg-surface hover:bg-caution-soft border border-caution-line text-caution-ink",
  negative: "bg-surface hover:bg-negative-soft border border-negative-line text-negative-ink",
};

/** No ground at all until the pointer arrives. For a control that sits inside
 *  something it must not compete with — a card's own header, a toolbar. */
export const GHOST: Record<Tone, string> = {
  neutral: "text-ink-body hover:bg-sunken",
  accent: "text-accent-ink hover:bg-accent-soft",
  positive: "text-positive-ink hover:bg-positive-soft",
  caution: "text-caution-ink hover:bg-caution-soft",
  negative: "text-negative-ink hover:bg-negative-soft",
};

/**
 * The keyboard-only focus ring, on every control in this directory.
 *
 * `focus-visible` rather than `focus`: a ring drawn on a mouse click is noise
 * the user did not ask for, and it is the reason people delete focus styling
 * altogether — which is how a keyboard user loses the caret entirely. The
 * offset is measured against `--page` rather than the control's own ground so
 * the ring stays visible on a control sitting on a tinted panel.
 */
export const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-ring "
  + "focus-visible:ring-offset-2 focus-visible:ring-offset-page";

/** Joins class fragments, dropping the empty ones, so a caller's `className`
 *  can be optional without every call site growing a ternary. */
export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
