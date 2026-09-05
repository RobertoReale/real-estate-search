/**
 * One place where the app tells the user something went wrong — or that
 * something they cannot see happened, and how to take it back.
 *
 * Before this, every surface reported its own failures: a red `<div>` under the
 * navbar for a failed write, a second one inside the filter bar for a failed
 * export, a third inside the property detail, a fourth per section of the
 * settings dialog. Four containers with four looks, none of which could say
 * anything a user could act on, and a fifth failure — the request that never
 * reached the backend at all — that read exactly like a rejected one. The
 * problem was never where the message was drawn: it was that nothing owned the
 * question "what should the user do about this?", so nothing ever answered it.
 *
 * What a toast raised here always carries:
 *
 * - **what happened**, in the app's words when the caller has better ones than
 *   the backend's (`doing`), and the backend's own sentence otherwise;
 * - **what to do**, chosen from the failure's shape — a request that never
 *   arrived, one that arrived and broke, and one that arrived and was refused
 *   need three different sentences and only one of them mentions the backend;
 * - **the one-click way to do it**, when there is one: `Try again` on anything
 *   re-runnable, and `Undo` on anything destructive the backend can reverse.
 *
 * Errors stay until they are dismissed, because a message that fades is one the
 * user was not looking at. Confirmations go on their own after
 * `DONE_MS` — long enough to reach an Undo without thinking about it, short
 * enough not to become furniture.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { translateCurrent, useT } from "../i18n";
import { ApiError } from "../services/api";
import { Close, ICON_SIZE, Success, Warning } from "../ui/icons";

/** How long a confirmation stays up. Sized by the Undo it may be carrying: the
 *  user has to notice the toast, read it, and decide — under four seconds and
 *  the affordance is a tease. */
const DONE_MS = 9000;

/** How many are shown at once. A failing backend can raise one per click, and a
 *  column of fifteen identical messages hides the screen it is reporting on. */
const MAX_VISIBLE = 3;

export interface ToastAction {
  /** The words on the button — already translated. */
  label: string;
  run: () => void | Promise<void>;
}

export interface ToastSpec {
  tone: "error" | "done";
  /** What happened, in one line. */
  text: string;
  /** What to do about it. */
  hint?: string;
  action?: ToastAction;
  /** A toast raised again under the same key replaces the first rather than
   *  stacking. The grid that cannot refresh says so once, not once per retry. */
  key?: string;
}

interface Raised extends ToastSpec {
  readonly id: number;
}

export interface FailOptions {
  /** What the app was trying to do, as a whole sentence, when the app can say
   *  it better than the backend can. The backend's own message is kept either
   *  way — it moves to the second line rather than being replaced. */
  doing?: string;
  /** Re-runs whatever failed. Becomes the toast's `Try again`. */
  retry?: () => void | Promise<void>;
  key?: string;
}

export interface Toasts {
  /** Full control, for a message that is neither a plain success nor a caught
   *  exception — a restart that reported it could not happen, say. */
  show: (spec: ToastSpec) => void;
  /** It worked. Optionally with the way to take it back. */
  done: (text: string, action?: ToastAction) => void;
  /** It did not. Turns anything thrown into a message and an instruction. */
  fail: (error: unknown, options?: FailOptions) => void;
}

/**
 * A thrown thing as a sentence.
 *
 * Providers answer with protocol jargon; translate the two that a user can
 * actually act on, and pass everything else through untouched. This moved here
 * from the settings dialog, which is where those two failures are met — but
 * they are not a property of that dialog, and every other caught error was
 * being rendered raw.
 */
export function errorText(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  if (/AUTHENTICATIONFAILED|Username and Password not accepted|535/i.test(raw)) {
    return translateCurrent("settings.errCredentials", { error: raw });
  }
  if (/timed out|timeout|Connection refused|getaddrinfo|Name or service not known/i.test(raw)) {
    return translateCurrent("settings.errNetwork", { error: raw });
  }
  return raw;
}

/** What to do about it, from the shape of the failure rather than from its
 *  words. `ApiError.status` is 0 when the request never reached the backend,
 *  which is the one case where the answer is about the machine and not about
 *  the request. */
export function adviceFor(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return translateCurrent("toast.adviceUnreachable");
    if (e.status >= 500) return translateCurrent("toast.adviceServer");
    return translateCurrent("toast.adviceRefused");
  }
  return translateCurrent("toast.adviceRetry");
}

const ToastContext = createContext<Toasts | null>(null);

/** Raising a toast with no provider above does nothing, deliberately: a unit
 *  test renders one component in isolation and must not have to mount the
 *  application shell to press a button. The provider is mounted once, in
 *  `main.tsx`, and the browser suite is what proves the real one is there. */
const SILENT: Toasts = { show: () => {}, done: () => {}, fail: () => {} };

export function useToasts(): Toasts {
  return useContext(ToastContext) ?? SILENT;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [raised, setRaised] = useState<Raised[]>([]);

  const dismiss = useCallback((id: number) => {
    setRaised((list) => list.filter((toast) => toast.id !== id));
  }, []);

  // Stable for the life of the app, so a toast raised from inside an effect
  // cannot be the reason that effect runs again.
  const api = useMemo<Toasts>(() => {
    const show = (spec: ToastSpec) => {
      setRaised((list) => {
        const id = (list[list.length - 1]?.id ?? 0) + 1;
        const kept = spec.key ? list.filter((t) => t.key !== spec.key) : list;
        return [...kept, { ...spec, id }].slice(-MAX_VISIBLE);
      });
    };
    return {
      show,
      done: (text, action) => show({ tone: "done", text, action }),
      fail: (error, options) => {
        const message = errorText(error);
        const advice = adviceFor(error);
        show({
          tone: "error",
          text: options?.doing ?? message,
          hint: options?.doing ? `${message} ${advice}` : advice,
          key: options?.key,
          action: options?.retry
            ? { label: translateCurrent("common.retry"), run: options.retry }
            : undefined,
        });
      },
    };
  }, []);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastHost toasts={raised} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

/** The stack itself. Fixed to the bottom of the viewport and above every
 *  overlay in the app, because the failure of an action taken inside a dialog
 *  has to be readable without closing the dialog. The container never takes a
 *  pointer event — only the toasts in it do — so an empty stack cannot swallow
 *  a click on the screen behind it. */
function ToastHost({ toasts, onDismiss }: {
  toasts: readonly Raised[];
  onDismiss: (id: number) => void;
}) {
  const t = useT();
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[200] flex flex-col items-center gap-2 p-3
        sm:items-end sm:p-4 pointer-events-none"
      aria-label={t("toast.region")}>
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastCard({ toast, onDismiss }: {
  toast: Raised;
  onDismiss: (id: number) => void;
}) {
  const t = useT();
  const failed = toast.tone === "error";

  useEffect(() => {
    if (failed) return; // an error waits to be read, and then dismissed
    const timer = setTimeout(() => onDismiss(toast.id), DONE_MS);
    return () => clearTimeout(timer);
  }, [failed, toast.id, onDismiss]);

  return (
    <div
      // `alert` interrupts, `status` waits for a pause: a failure is worth the
      // interruption and a confirmation is not.
      role={failed ? "alert" : "status"}
      className={`glass pointer-events-auto w-full max-w-md rounded-2xl p-3.5 shadow-lg
        animate-fade-in flex items-start gap-3 text-sm ${failed
          ? "border-negative-line bg-negative-tint"
          : "border-positive-line bg-positive-tint"}`}>
      <span className="shrink-0 leading-6">
        {failed ? <Warning size={ICON_SIZE.lead} /> : <Success size={ICON_SIZE.lead} />}
      </span>
      <div className="min-w-0 flex-1">
        <p className={`font-medium break-words ${failed
          ? "text-negative-ink-strong"
          : "text-positive-ink"}`}>
          {toast.text}
        </p>
        {toast.hint && <p className="t-muted text-xs mt-1 break-words">{toast.hint}</p>}
        {toast.action && (
          <button data-action="toast.action"
            type="button"
            className="btn-ghost text-xs mt-2 px-2.5 py-1 rounded-lg border
              border-line-strong"
            onClick={() => {
              // Dismissed first: whatever the action does, this message is
              // about what already happened, and leaving it up while an Undo
              // runs invites a second press of the same Undo.
              onDismiss(toast.id);
              void toast.action?.run();
            }}>
            {toast.action.label}
          </button>
        )}
      </div>
      <button data-action="toast.dismiss"
        type="button"
        className="btn-ghost shrink-0 py-0.5 px-2 leading-none"
        aria-label={t("toast.dismiss")}
        onClick={() => onDismiss(toast.id)}>
        <Close size={16} />
      </button>
    </div>
  );
}
