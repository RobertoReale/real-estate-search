/**
 * A small, tinted label. A fact about something, never a control.
 *
 * That last clause is the whole design. A chip renders a `<span>` and takes no
 * handler, because the app already has a shape for "a small thing you can
 * press" — `Button size="sm"` — and the moment a chip can be clicked, nothing
 * on screen distinguishes the tag that *is* on a listing from the tag you can
 * *put* on one. D.2 wants removable filter chips; the removal is a `Button`
 * beside the chip, not the chip growing a handler.
 *
 * Three of the tones judge (`positive`, `caution`, `negative`), two orient
 * (`accent`, `info`), and three only identify (`neutral`, `tag`, `rent`). The
 * separation is inherited from `tokens.css` and matters for the same reason it
 * does there: nothing should be able to render "Idealista" in the colour that
 * means "good deal".
 */
import type { ReactNode } from "react";

import { cx } from "./tone";

export type ChipTone =
  | "accent" | "positive" | "caution" | "negative"
  | "info" | "neutral" | "tag" | "rent";

const TONES: Record<ChipTone, string> = {
  accent: "bg-accent-soft text-accent-ink",
  positive: "bg-positive-soft text-positive-ink",
  caution: "bg-caution-soft text-caution-ink",
  negative: "bg-negative-soft text-negative-ink",
  info: "bg-info-soft text-info-ink",
  neutral: "bg-neutral-soft text-neutral-ink",
  tag: "bg-tag-soft text-tag-ink",
  rent: "bg-rent-soft text-rent-ink",
};

/** The dot is a second channel for the same statement, for the reader who
 *  cannot separate the tints. It is `aria-hidden` because it repeats the text
 *  beside it rather than adding to it. */
const DOTS: Record<ChipTone, string> = {
  accent: "bg-accent",
  positive: "bg-positive-dot",
  caution: "bg-caution-dot",
  negative: "bg-negative-dot",
  info: "bg-info-marker",
  neutral: "bg-neutral-dot",
  tag: "bg-tag",
  rent: "bg-rent",
};

const SIZES = {
  sm: "text-2xs px-2 py-0.5 gap-1",
  md: "text-xs px-2.5 py-1 gap-1.5",
} as const;

export interface ChipProps {
  tone?: ChipTone;
  size?: keyof typeof SIZES;
  /** A leading status dot in the same tone. */
  dot?: boolean;
  className?: string;
  children: ReactNode;
}

export function Chip({ tone = "neutral", size = "sm", dot = false, className, children }: ChipProps) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-chip font-medium whitespace-nowrap",
        SIZES[size], TONES[tone], className,
      )}>
      {dot && <span aria-hidden="true" className={cx("h-1.5 w-1.5 rounded-pill", DOTS[tone])} />}
      {children}
    </span>
  );
}
