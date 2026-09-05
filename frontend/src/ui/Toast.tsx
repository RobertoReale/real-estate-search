/**
 * The drawing of a toast. Not the deciding of one.
 *
 * B.5 already built the system: `components/Toast.tsx` owns *when* a message is
 * raised, what advice goes on it, which failures collapse into one, and how long
 * a confirmation stays. None of that is repeated here and none of it should be —
 * this file is the surface that system renders onto, split out for the reason
 * every primitive in this directory is split out: so the next screen that needs
 * to say something does not draw its own.
 *
 * What Radix contributes is the part the hand-rolled host does not have, and it
 * is entirely about the keyboard. A toast appears without the user doing
 * anything, so it cannot steal focus — which means that by default nobody
 * navigating by keyboard can ever reach the **Undo** button on it. Radix gives
 * the viewport a hotkey (F8 by default) that jumps to the stack, makes the
 * toasts a focus scope you can Tab through and leave, and puts the whole thing
 * in a live region with the right politeness. `role="status"` for a
 * confirmation and `role="alert"` for a failure comes from `type`.
 *
 * `ToastProvider` and `ToastViewport` are separate exports because the viewport
 * has to be mounted once, at the root, and the provider has to be above
 * everything that raises one.
 */
import { Toast as ToastPrimitive } from "radix-ui";
import type { ReactNode } from "react";

import { cx, FOCUS_RING } from "./tone";

export interface ToastProviderProps {
  /** Prefixed to every announcement, so a reader hears what kind of thing has
   *  just interrupted before it hears the message. Translated by the caller —
   *  the app's default language is Italian. */
  label: string;
  /** Default lifetime in milliseconds. A toast may override it, and an error
   *  passes `Infinity`: a message that fades is one the user was not looking at. */
  duration?: number;
  children: ReactNode;
}

export function ToastProvider({ label, duration = 9000, children }: ToastProviderProps) {
  return (
    <ToastPrimitive.Provider label={label} duration={duration} swipeDirection="right">
      {children}
    </ToastPrimitive.Provider>
  );
}

/** The stack. Bottom of the viewport, above every overlay in the app (dialogs
 *  and sheets sit at 100, popovers and tooltips at 110–120), because a write
 *  that fails while a dialog is open has to be readable without closing the
 *  dialog and losing what was typed. The container itself takes no pointer
 *  events, so an empty stack cannot swallow a click on the screen behind it. */
export function ToastViewport({ label, className }: {
  /** Names the region and tells the user how to get into it. Radix substitutes
   *  the hotkey for `{hotkey}`, so the caller writes something like
   *  `"Notifiche ({hotkey})"`; without it the region keeps Radix's English
   *  default, which is one of the few strings a user can hear but not see. */
  label: string;
  className?: string;
}) {
  return (
    <ToastPrimitive.Viewport
      label={label}
      className={cx(
        "pointer-events-none fixed inset-x-0 bottom-0 z-[200] m-0 flex list-none",
        "flex-col items-center gap-2 p-3 outline-none sm:items-end sm:p-4",
        className,
      )} />
  );
}

export interface ToastProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tone: "done" | "error";
  title: ReactNode;
  /** What to do about it. */
  description?: ReactNode;
  /** The one-click way to do it. `altText` is what a screen-reader user is told
   *  they can do when the toast is not reachable — Radix requires it, and the
   *  requirement is the right one: "Undo" alone says nothing about what. */
  action?: { label: string; altText: string; onSelect: () => void };
  closeLabel: string;
  duration?: number;
}

const TONES = {
  done: "border-positive-line bg-positive-tint",
  error: "border-negative-line bg-negative-tint",
} as const;

const TITLES = {
  done: "text-positive-ink",
  error: "text-negative-ink-strong",
} as const;

export function Toast({
  open, onOpenChange, tone, title, description, action, closeLabel, duration,
}: ToastProps) {
  return (
    <ToastPrimitive.Root
      open={open}
      onOpenChange={onOpenChange}
      duration={duration}
      // `foreground` interrupts, `background` waits for a pause: a failure is
      // worth the interruption and a confirmation is not.
      type={tone === "error" ? "foreground" : "background"}
      className={cx(
        "pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-card border",
        "bg-surface/90 p-3.5 text-sm shadow-e2 backdrop-blur-xl",
        TONES[tone],
      )}>
      <div className="min-w-0 flex-1">
        <ToastPrimitive.Title className={cx("font-medium break-words", TITLES[tone])}>
          {title}
        </ToastPrimitive.Title>
        {description && (
          <ToastPrimitive.Description className="mt-1 break-words text-xs text-ink-muted">
            {description}
          </ToastPrimitive.Description>
        )}
        {action && (
          <ToastPrimitive.Action altText={action.altText} asChild>
            <button type="button" onClick={action.onSelect}
              className={cx(
                "mt-2 inline-flex items-center rounded-control border border-line-strong",
                "bg-surface px-2.5 py-1 text-xs font-medium text-ink-body transition",
                "hover:bg-sunken", FOCUS_RING,
              )}>
              {action.label}
            </button>
          </ToastPrimitive.Action>
        )}
      </div>
      <ToastPrimitive.Close aria-label={closeLabel}
        className={cx(
          "shrink-0 rounded-control p-1 text-ink-faint transition hover:text-ink-body",
          FOCUS_RING,
        )}>
        <svg aria-hidden="true" viewBox="0 0 12 12"
          className="h-3 w-3 fill-none stroke-current stroke-2">
          <path d="m2 2 8 8M10 2l-8 8" strokeLinecap="round" />
        </svg>
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}
