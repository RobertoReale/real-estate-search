import { useEffect, useState, type ReactNode } from "react";
import { useT } from "../i18n";
import { api } from "../services/api";
import { authToken, setAuthRequiredHandler } from "../services/api";

/** Shows a token prompt whenever the backend answers 401 (optional API auth is
 *  enabled — invariant 14 relaxed to "bind address OR token"). When auth is off,
 *  no request ever 401s and this is inert, so the common case is untouched. */
export default function AuthGate({ children }: { children: ReactNode }) {
  const t = useT();
  const [needAuth, setNeedAuth] = useState(false);
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setAuthRequiredHandler(() => setNeedAuth(true));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setChecking(true);
    setError("");
    authToken.set(token.trim());
    try {
      await api.getSettings(); // 200 proves the token is accepted
      window.location.reload(); // reload so every data load re-runs authenticated
    } catch {
      authToken.clear();
      setError(t("auth.rejected"));
      setChecking(false);
    }
  }

  return (
    <>
      {children}
      {needAuth && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <form onSubmit={submit}
            className="glass rounded-2xl max-w-sm w-full p-6 space-y-4">
            <div>
              <h2 className="text-lg font-bold">{t("auth.title")}</h2>
              <p className="text-xs t-dim mt-1">{t("auth.hint")}</p>
            </div>
            <input className="input w-full" type="password" autoFocus
              placeholder={t("auth.placeholder")}
              value={token} onChange={(e) => setToken(e.target.value)} />
            {error && (
              <p className="text-sm rounded-lg px-3 py-2 bg-rose-500/10 text-rose-700 dark:text-rose-300">
                {error}
              </p>
            )}
            <button className="btn-primary w-full" type="submit"
              disabled={checking || !token.trim()}>
              {checking ? t("auth.checking") : t("auth.unlock")}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
