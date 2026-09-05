/**
 * A box that is ticked, or is not, or is neither.
 *
 * The third state is the reason this is not a native `<input type="checkbox">`.
 * The batch bar's "select all" is indeterminate whenever some of the results
 * are selected and not all of them, and a native checkbox can only be put into
 * that state by assigning `el.indeterminate` from an effect on a ref — which
 * React does not model, so it is a line of imperative DOM in the middle of a
 * render and it is missing today. Radix takes `checked="indeterminate"` as a
 * value like any other and puts `aria-checked="mixed"` on the element.
 *
 * The label is a prop rather than a sibling because a checkbox's label sits
 * *beside* it, not above it — so the `Field` wrapper, which stacks, is the wrong
 * shape. What `Field` still supplies is the id, and with it the hint and the
 * error, so a checkbox inside one is described exactly like the inputs around
 * it.
 */
import { Checkbox as CheckboxPrimitive, Label } from "radix-ui";
import { useId, type ReactNode } from "react";

import { useFieldWiring } from "./Field";
import { cx, FOCUS_RING } from "./tone";

export interface CheckboxProps {
  checked: boolean | "indeterminate";
  onCheckedChange: (checked: boolean | "indeterminate") => void;
  /** The words beside the box. Omit only when an `aria-label` says the same
   *  thing — a checkbox with neither is a control nobody can name. */
  label?: ReactNode;
  disabled?: boolean;
  name?: string;
  className?: string;
  "aria-label"?: string;
  "data-action"?: string;
}

export function Checkbox({
  checked, onCheckedChange, label, disabled, name, className,
  "aria-label": ariaLabel, "data-action": dataAction,
}: CheckboxProps) {
  const fallback = useId();
  const field = useFieldWiring();
  const id = field?.id ?? fallback;

  return (
    <div className={cx("flex items-center gap-2", className)}>
      <CheckboxPrimitive.Root
        id={id}
        name={name}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        required={field?.required}
        aria-label={ariaLabel}
        aria-describedby={field?.describedBy}
        aria-invalid={field?.invalid || undefined}
        data-action={dataAction}
        className={cx(
          // 1.15rem is what `index.css` enlarges the app's native checkboxes to
          // on a phone; kept at every width here because a control drawn by
          // this app rather than by the platform has no reason to be smaller
          // than a fingertip on a laptop either.
          "flex h-[1.15rem] w-[1.15rem] shrink-0 items-center justify-center rounded-[0.3rem]",
          "border border-line-strong bg-surface transition",
          "data-[state=checked]:border-accent data-[state=checked]:bg-accent",
          "data-[state=indeterminate]:border-accent data-[state=indeterminate]:bg-accent",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          FOCUS_RING,
        )}>
        <CheckboxPrimitive.Indicator className="text-on-solid">
          {checked === "indeterminate"
            ? <svg aria-hidden="true" viewBox="0 0 12 12" className="h-2.5 w-2.5 stroke-current stroke-2">
                <path d="M2 6h8" strokeLinecap="round" />
              </svg>
            : <svg aria-hidden="true" viewBox="0 0 12 12"
                className="h-2.5 w-2.5 fill-none stroke-current stroke-2">
                <path d="m1.5 6.5 3 3 6-6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>}
        </CheckboxPrimitive.Indicator>
      </CheckboxPrimitive.Root>
      {label && (
        <Label.Root htmlFor={id} className="text-sm text-ink-body select-none">
          {label}
        </Label.Root>
      )}
    </div>
  );
}
