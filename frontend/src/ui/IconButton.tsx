/**
 * A button whose whole label is a picture.
 *
 * Which means it has no label, and that is the only thing this component adds
 * to `Button`: `label` is a required prop, not an optional one. An icon-only
 * control without an accessible name is announced by a screen reader as
 * "button" and nothing else — the app currently has several, and every one of
 * them is a control somebody cannot use. Making the name required is the
 * cheapest possible place to catch that: the type checker, before the commit,
 * rather than an axe violation in the browser suite afterwards.
 *
 * The same string becomes the tooltip's title, so the sighted user who cannot
 * guess the glyph gets the same sentence as the user who cannot see it.
 */
import { Button, type ButtonBase, type Emphasis } from "./Button";

export type IconButtonProps =
  Omit<ButtonBase, "size" | "block" | "aria-label" | "title">
  & Emphasis
  & {
    /** What this button does, in words. Required — see the note above. */
    label: string;
    size?: "sm" | "md";
  };

export function IconButton({ label, size = "md", ...rest }: IconButtonProps) {
  return <Button aria-label={label} title={label} size={`icon-${size}`} {...rest} />;
}
