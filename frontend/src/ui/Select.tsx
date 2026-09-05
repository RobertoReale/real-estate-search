/**
 * Choosing one of a list.
 *
 * Radix rather than a native `<select>`, and the trade is worth stating because
 * it is not obviously the right way round. A native select is the most
 * accessible control in the platform and the best one on a phone, where the
 * operating system draws a wheel. What it cannot do is be styled: the popup is
 * the browser's, so a dark theme shows a light menu, an option cannot carry a
 * second line, and the trigger cannot look like the text input beside it. The
 * filter bar has selects and inputs side by side, and half of them ignoring the
 * theme is the loudest remaining sign that this is a prototype.
 *
 * What Radix gives back is the part that is genuinely hard: the listbox roles,
 * the typeahead, Home/End/arrow traversal, the focus returning to the trigger
 * on close, and the click-outside and Escape handling. None of that is written
 * here, which is the point of the dependency.
 *
 * The options are a prop rather than children. A `<Select>` in this app always
 * renders a flat list of value/label pairs out of a translation dictionary, and
 * a compositional API would mean every one of the app's dozen selects
 * re-implementing the same `.map`.
 */
import { Select as SelectPrimitive } from "radix-ui";

import { useFieldWiring } from "./Field";
import { CONTROL_SURFACE } from "./Input";
import { cx, FOCUS_RING } from "./tone";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: readonly SelectOption[];
  /** Shown when `value` is the empty string. Radix treats `""` as "nothing
   *  chosen", which is why no option may carry it as a value. */
  placeholder?: string;
  name?: string;
  disabled?: boolean;
  className?: string;
  /** Only needed outside a `Field`, which supplies the label otherwise. */
  "aria-label"?: string;
  "data-action"?: string;
}

export function Select({
  value, onValueChange, options, placeholder, name, disabled, className,
  "aria-label": ariaLabel, "data-action": dataAction,
}: SelectProps) {
  const field = useFieldWiring();
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange} name={name}
      disabled={disabled} required={field?.required}>
      <SelectPrimitive.Trigger
        id={field?.id}
        aria-label={ariaLabel}
        aria-describedby={field?.describedBy}
        aria-invalid={field?.invalid || undefined}
        data-action={dataAction}
        className={cx(CONTROL_SURFACE, FOCUS_RING, "flex items-center justify-between gap-2 text-left",
          className)}>
        <SelectPrimitive.Value placeholder={placeholder} />
        {/* The caret is drawn rather than typed: an ASCII "▾" is a glyph whose
            size and baseline are the font's business, and it lands differently
            on every platform the app runs on. C.3 replaces the app's emoji for
            the same reason; a primitive should not be waiting for it. */}
        <SelectPrimitive.Icon asChild>
          <svg aria-hidden="true" viewBox="0 0 12 12" className="h-3 w-3 shrink-0 fill-ink-faint">
            <path d="M6 8.5 1.5 4h9z" />
          </svg>
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className="z-[110] max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden
            rounded-control border border-line bg-raised shadow-e3">
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item key={option.value} value={option.value}
                disabled={option.disabled}
                className="relative flex cursor-default select-none items-center rounded-chip
                  py-1.5 pl-7 pr-3 text-sm text-ink-body outline-none
                  data-[highlighted]:bg-accent-soft data-[highlighted]:text-accent-ink
                  data-[disabled]:opacity-50">
                <SelectPrimitive.ItemIndicator className="absolute left-2">
                  <svg aria-hidden="true" viewBox="0 0 12 12"
                    className="h-3 w-3 fill-none stroke-current stroke-2">
                    <path d="m1.5 6.5 3 3 6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
