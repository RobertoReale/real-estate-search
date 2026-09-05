/**
 * The button. One of them.
 *
 * The batch bar is the reason this file exists. It carried six buttons and six
 * different class strings: two that hovered towards `caution` for actions that
 * are not cautions (add and remove a favourite), one that hovered towards
 * `negative` for hiding, one for stopping, one that toggled its own background
 * to the accent, and one — the availability check — that had no border, no
 * hover and **no focus ring at all**, so the only way to reach it was with a
 * pointer. None of that was decided. It accumulated, one copy-paste at a time,
 * and nothing in the build could tell a variant somebody meant from one they
 * mistyped.
 *
 * What replaces it is two declared axes (`variant` × `tone`, see `tone.ts`) and
 * a size. Everything else a button needs — the focus ring, the disabled state,
 * the touch target on a phone — is decided here once and cannot be forgotten at
 * a call site.
 *
 * `asChild` renders the styling onto whatever child is passed instead of a
 * `<button>`, which is how a link becomes a button without a `<button>` wrapping
 * an `<a>`: the element that navigates has to be the anchor, or the middle-click
 * and the "copy link address" that a user expects from a link are gone.
 */
import { Slot } from "radix-ui";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cx, FOCUS_RING, GHOST, OUTLINE, SOLID, type SolidTone, type Tone } from "./tone";

/** `icon-*` are square and paddingless, and exist here rather than in
 *  `IconButton` for a mechanical reason: Tailwind resolves `p-0` against `px-3`
 *  by stylesheet order, not by the order of the class attribute, so an
 *  `IconButton` that overrode the padding of a text size would win or lose
 *  depending on how the CSS happened to be emitted. A size that is square from
 *  the start cannot be half-overridden. */
export type Size = "sm" | "md" | "icon-sm" | "icon-md";

const SIZES: Record<Size, string> = {
  // Dense rows — a toolbar, a card's own actions. Deliberately without a
  // minimum height: the batch bar and the filter rail are measured for
  // horizontal overflow at 390 px by the browser suite, and growing every
  // small button is a layout change wearing the clothes of a token change.
  sm: "text-xs px-3 py-1.5",
  // The default. `min-h-touch` is the 44 px a fingertip needs, dropped at `sm`
  // where the pointer is precise and the extra height only loosens the row.
  md: "text-sm px-4 py-2 min-h-touch sm:min-h-0",
  "icon-sm": "text-xs h-8 w-8",
  "icon-md": "text-sm h-10 w-10",
};

const BASE =
  "inline-flex items-center justify-center gap-1.5 font-medium rounded-control "
  + "transition disabled:opacity-50 disabled:cursor-not-allowed "
  + "disabled:pointer-events-none";

export type ButtonBase = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "color"> & {
  size?: Size;
  /** Fills the width of whatever it is in. A phone's primary action, mostly. */
  block?: boolean;
  /** Render the styling onto the child element instead of a `<button>`. */
  asChild?: boolean;
  children?: ReactNode;
};

/** How loud, and about what. Written as a union rather than two independent
 *  props so that `variant="solid" tone="caution"` does not compile — see
 *  `SolidTone` in `tone.ts` for why that combination has no correct drawing
 *  rather than an undrawn one. Exported because `IconButton` is the same
 *  question asked of a control with no words in it. */
export type Emphasis =
  | { variant: "solid"; tone?: SolidTone }
  | { variant?: "outline" | "ghost"; tone?: Tone };

export type ButtonProps = ButtonBase & Emphasis;

export function Button({
  variant = "outline",
  tone = "neutral",
  size = "md",
  block = false,
  asChild = false,
  className,
  ...rest
}: ButtonProps) {
  const skin =
    variant === "solid" ? SOLID[tone as SolidTone]
    : variant === "ghost" ? GHOST[tone]
    : OUTLINE[tone];

  // Only `<button>` gets a default `type`. Forcing one onto an `asChild`
  // anchor would put an invalid attribute on it, and a `<button>` inside a
  // form defaults to `submit`, which is how a filter control ends up
  // reloading the page.
  if (asChild) {
    return (
      <Slot.Root className={cx(BASE, SIZES[size], skin, FOCUS_RING, block && "w-full", className)}
        {...rest} />
    );
  }
  return (
    <button
      type="button"
      className={cx(BASE, SIZES[size], skin, FOCUS_RING, block && "w-full", className)}
      {...rest} />
  );
}
