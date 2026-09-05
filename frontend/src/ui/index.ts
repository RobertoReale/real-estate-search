/**
 * The primitives. Everything the interface is drawn with, and nothing about
 * what it means.
 *
 * The rule that keeps this directory worth having: a component belongs here
 * only if it knows nothing about property listings. A `Button` does not know
 * what it saves; a `Chip` does not know that garnet means a price drop. The
 * moment a file in here mentions a listing, a portal or a price it has become a
 * component, and `src/components/` is where it goes.
 *
 * Underneath is Radix, and the reason is narrow and worth stating once. Focus
 * trapping, restoring focus on close, Escape handling, roving tabindex, the
 * `aria-*` wiring between a control and its label, and the pointer-versus-key
 * distinctions that make `focus-visible` behave — all of it is the kind of code
 * that looks finished long before it is correct, and every screen that rolls its
 * own gets it wrong differently. Deferring to a library that has been audited
 * for it means those bugs are absent here rather than fixed here.
 *
 * Import from this barrel, not from the files: `import { Button, Field } from
 * "../ui"`. It is what makes the set discoverable and what makes it obvious in
 * review when a screen reaches past the set for something the set should have.
 */
export { Button } from "./Button";
export type { ButtonBase, ButtonProps, Emphasis, Size } from "./Button";
export { Card, CardHeader } from "./Card";
export type { CardProps } from "./Card";
export { Checkbox } from "./Checkbox";
export type { CheckboxProps } from "./Checkbox";
export { Chip } from "./Chip";
export type { ChipProps, ChipTone } from "./Chip";
export { Dialog } from "./Dialog";
export type { DialogProps } from "./Dialog";
export { EmptyState } from "./EmptyState";
export type { EmptyStateProps } from "./EmptyState";
export { Field, useFieldWiring } from "./Field";
export type { FieldProps, FieldWiring } from "./Field";
export { IconButton } from "./IconButton";
export type { IconButtonProps } from "./IconButton";
export { CONTROL_SURFACE, Input, Textarea } from "./Input";
export type { InputProps, TextareaProps } from "./Input";
export { Popover } from "./Popover";
export type { PopoverProps } from "./Popover";
export { Select } from "./Select";
export type { SelectOption, SelectProps } from "./Select";
export { Sheet } from "./Sheet";
export type { SheetProps } from "./Sheet";
export { Skeleton } from "./Skeleton";
export type { SkeletonProps } from "./Skeleton";
export { Tabs } from "./Tabs";
export type { TabItem, TabsProps } from "./Tabs";
export { Toast, ToastProvider, ToastViewport } from "./Toast";
export type { ToastProps, ToastProviderProps } from "./Toast";
export { Tooltip } from "./Tooltip";
export type { TooltipProps } from "./Tooltip";
export { cx, FOCUS_RING } from "./tone";
export type { SolidTone, Tone, Variant } from "./tone";
