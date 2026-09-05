/**
 * The wiring around a form control: its label, its hint, and what is wrong with
 * it.
 *
 * The point is that none of that wiring is typed at a call site. A label is
 * only a label when `htmlFor` names the control's `id`; a hint is only read
 * aloud when `aria-describedby` points at it; an error is only an error when
 * `aria-invalid` says so *and* the message is in the description. Four
 * attributes, three generated ids, and any one of them missing degrades
 * silently — the screen looks right and the field is unusable without sight.
 * The app has that bug in several places today, and it has it because the
 * correct version is four things to remember.
 *
 * So `Field` generates the ids and publishes them on a context, and `Input`,
 * `Select` and `Checkbox` read them. A field written as
 *
 *     <Field label="Prezzo massimo" hint="In euro" error={tooLow}>
 *       <Input value={price} onChange={…} />
 *     </Field>
 *
 * is wired correctly because there was no other way to write it.
 *
 * The label itself is Radix's, which is one detail's worth of behaviour this
 * codebase would otherwise have to remember: a native `<label>` forwards a
 * click to its control, including a click that was the *end of a text
 * selection* — so dragging to select the label's words toggles the checkbox
 * beside it. Radix suppresses that one case and nothing else.
 */
import { Label } from "radix-ui";
import { createContext, useContext, useId, type ReactNode } from "react";

import { cx } from "./tone";

export interface FieldWiring {
  /** The id the label points at, which the control must adopt. */
  readonly id: string;
  /** Space-separated ids of the hint and the error, or undefined for neither. */
  readonly describedBy: string | undefined;
  readonly invalid: boolean;
  readonly required: boolean;
}

const FieldContext = createContext<FieldWiring | null>(null);

/** Null outside a `Field`. A bare `<Input>` is a legitimate thing — a search box
 *  with a visible placeholder and its own `aria-label` — and must not have to
 *  invent a wrapper to render. */
export function useFieldWiring(): FieldWiring | null {
  return useContext(FieldContext);
}

export interface FieldProps {
  label: ReactNode;
  /** What the value is for, or what shape it takes. Always present when set —
   *  a hint that only appears once the user is wrong is advice arriving late. */
  hint?: ReactNode;
  /** What is wrong with the current value. Its presence is what makes the
   *  control invalid; there is no separate `invalid` prop to fall out of step
   *  with the message. */
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

export function Field({ label, hint, error, required = false, className, children }: FieldProps) {
  const base = useId();
  const id = `${base}-control`;
  const hintId = hint ? `${base}-hint` : undefined;
  const errorId = error ? `${base}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <Label.Root htmlFor={id} className="text-xs font-medium text-ink-body">
        {label}
        {required && <span aria-hidden="true" className="ml-0.5 text-negative-ink">*</span>}
      </Label.Root>
      <FieldContext.Provider value={{ id, describedBy, invalid: Boolean(error), required }}>
        {children}
      </FieldContext.Provider>
      {hint && <p id={hintId} className="text-2xs text-ink-muted">{hint}</p>}
      {/* `role="alert"` so a message that appears after the user has moved on is
          still announced. The text is in `aria-describedby` as well, which is
          what the reader gets when they come *back* to the field. */}
      {error && <p id={errorId} role="alert" className="text-2xs text-negative-ink">{error}</p>}
    </div>
  );
}
