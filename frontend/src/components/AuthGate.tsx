import { useEffect, useState, type ReactNode } from "react";
import { useT } from "../i18n";
import { Locked } from "../ui/icons";
import { useVerifyToken } from "../queries/settings";
import { authToken, setAuthRequiredHandler } from "../services/api";

/** Shows a token prompt whenever the backend answers 401 (optional API auth is
 *  enabled — invariant 14 relaxed to "bind address OR token"). When auth is off,
 *  no request ever 401s and this is inert, so the common case is untouched. */
export default function AuthGate({ children }: { children: ReactNode }) {
  const t = useT();
  const [needAuth, setNeedAuth] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const verify = useVerifyToken();

  useEffect(() => {
    setAuthRequiredHandler(() => setNeedAuth(true));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    authToken.set(token.trim());
    try {
      await verify.mutateAsync(); // a 200 proves the token is accepted
      window.location.reload(); // reload so every data load re-runs authenticated
    } catch {
      authToken.clear();
      setError(t("auth.rejected"));
    }
  }

  return (
    <>
      {children}
      {needAuth && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-overlay backdrop-blur-sm">
          <form data-action="auth.submit" onSubmit={submit}
            className="glass rounded-2xl max-w-sm w-full p-6 space-y-4">
            <div>
              <h2 className="flex items-center gap-1.5 text-lg font-bold">
                <Locked className="shrink-0" /> {t("auth.title")}
              </h2>
              <p className="text-xs t-dim mt-1">{t("auth.hint")}</p>
            </div>
            {/* The one failure that stays on the form rather than becoming a
                message: it is about the field directly above it, the thing to
                do about it is to type a different token, and the gate is drawn
                over everything else — including the toasts. */}
            <input data-action="auth.token" className="input w-full" type="password" autoFocus
              placeholder={t("auth.placeholder")}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "auth-error" : undefined}
              value={token} onChange={(e) => setToken(e.target.value)} />
            {error && (
              <p id="auth-error" role="alert" className="text-sm accent-bad">{error}</p>
            )}
            <button className="btn-primary w-full" type="submit"
              disabled={verify.isPending || !token.trim()}>
              {verify.isPending ? t("auth.checking") : t("auth.unlock")}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
