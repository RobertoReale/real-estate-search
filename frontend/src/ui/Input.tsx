/**
 * A text box, and the two things it must not get wrong.
 *
 * **It adopts the field's wiring.** The id, the description and the invalid
 * flag come from the `Field` above it rather than from the call site; see
 * `Field.tsx` for why that is not a convenience. A caller may still override
 * any of them — an `id` or an `aria-label` passed explicitly wins, because the
 * spread comes last — which is what makes a `<Input>` outside a `Field` a
 * legitimate thing rather than a broken one.
 *
 * **It is 16 px on a phone.** iOS Safari zooms the page in when a focused field
 * has text under 16 px, and does not zoom back out; the user is left on a
 * viewport 40% too wide with no obvious way back. `text-base sm:text-sm` is
 * exactly the rule `index.css` spells as a media query — Tailwind's `sm` starts
 * at 40rem, which is the same boundary — carried here so the primitive is
 * correct on its own rather than correct because of a stylesheet somewhere
 * else.
 */
import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

import { useFieldWiring } from "./Field";
import { cx } from "./tone";

/** Shared by the input and the textarea, and by `Select`'s trigger — the three
 *  have to look like the same control or a form reads as three forms. */
export const CONTROL_SURFACE =
  "w-full bg-surface border border-line-strong rounded-control px-3 py-2 "
  + "text-base sm:text-sm text-ink placeholder-ink-hint outline-none transition "
  + "focus:border-accent-line focus:ring-2 focus:ring-accent-tint "
  + "disabled:opacity-50 disabled:cursor-not-allowed "
  + "aria-invalid:border-negative-line aria-invalid:focus:ring-negative-tint";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...rest }: InputProps) {
  const field = useFieldWiring();
  return (
    <input
      id={field?.id}
      aria-describedby={field?.describedBy}
      aria-invalid={field?.invalid || undefined}
      required={field?.required}
      className={cx(CONTROL_SURFACE, className)}
      {...rest} />
  );
}

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className, ...rest }: TextareaProps) {
  const field = useFieldWiring();
  return (
    <textarea
      id={field?.id}
      aria-describedby={field?.describedBy}
      aria-invalid={field?.invalid || undefined}
      required={field?.required}
      className={cx(CONTROL_SURFACE, "resize-y", className)}
      {...rest} />
  );
}
