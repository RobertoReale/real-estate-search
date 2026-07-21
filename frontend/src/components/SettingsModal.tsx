import { useEffect, useState, type ReactNode } from "react";
import { formatDate, formatDateTime, translateCurrent, useT } from "../i18n";
import { api, authToken } from "../services/api";
import type { Settings } from "../types";

interface Props {
  onClose: () => void;
}

/** Which section a success/error message belongs to, so it can render there. */
type Section = "telegram" | "email" | "imap" | "global" | "data";

interface Feedback {
  where: Section;
  ok: boolean;
  text: string;
}

function HelpSteps({ summary, steps }: { summary: string; steps: ReactNode[] }) {
  return (
    <details className="text-xs t-muted mb-3 rounded-lg panel">
      <summary className="cursor-pointer px-3 py-2 select-none hover:text-slate-800 dark:hover:text-slate-200 transition">
        {summary}
      </summary>
      <ol className="px-3 pb-3 pt-1 space-y-1.5 list-decimal list-inside">
        {steps.map((s, i) => <li key={i}>{s}</li>)}
      </ol>
    </details>
  );
}

function Link({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer"
      className="underline underline-offset-2 hover:text-slate-800 dark:hover:text-slate-200">
      {children}
    </a>
  );
}

/** Whether a write-only secret (API key, token, password, cookie) is currently
 *  stored on the server. These inputs are masked and the backend never returns
 *  the value, so the only previous cue was faint placeholder text — this makes
 *  the state unmistakable. `dirty` = the field holds unsaved input that will
 *  replace what is stored; `since` (when known) adds the save date. */
function SecretStatus({ set, since, dirty }: { set?: boolean; since?: string; dirty?: boolean }) {
  const t = useT();
  if (dirty) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full chip-amber">
        {t("settings.secretDirty")}
      </span>
    );
  }
  if (set) {
    return (
      <span title={since
        ? t("settings.secretLastSaved", { date: formatDateTime(since) })
        : t("settings.secretSavedTitle")}
        className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full chip-emerald">
        {since
          ? t("settings.secretSavedOn", { date: formatDate(since) })
          : t("settings.secretSaved")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full chip-slate">
      {t("settings.secretNotSet")}
    </span>
  );
}

export default function SettingsModal({ onClose }: Props) {
  const t = useT();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [tgEnabled, setTgEnabled] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [emailFrom, setEmailFrom] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState(993);
  const [imapUser, setImapUser] = useState("");
  const [imapPassword, setImapPassword] = useState("");
  const [autoImport, setAutoImport] = useState(false);
  const [autoImportHours, setAutoImportHours] = useState(24);
  const [interval, setIntervalMin] = useState(60);
  const [scanPaused, setScanPaused] = useState(false);
  const [healthAfter, setHealthAfter] = useState(3);
  const [keywords, setKeywords] = useState("");
  const [matchEnabled, setMatchEnabled] = useState(false);
  const [dreamMaxPrice, setDreamMaxPrice] = useState(0);
  const [dreamMinRooms, setDreamMinRooms] = useState(0);
  const [dreamMinSqm, setDreamMinSqm] = useState(0);
  const [dreamMinFloor, setDreamMinFloor] = useState(0);
  const [dreamKeywords, setDreamKeywords] = useState("");
  const [dreamZones, setDreamZones] = useState("");
  const [nlBackend, setNlBackend] = useState("deterministic");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [proxyUrl, setProxyUrl] = useState("");
  const [proxyUrls, setProxyUrls] = useState("");
  const [scrapeApiProvider, setScrapeApiProvider] = useState("scrapfly");
  const [scrapeApiKey, setScrapeApiKey] = useState("");
  const [scrapeApiMode, setScrapeApiMode] = useState("fallback");
  const [datadomeCookie, setDatadomeCookie] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [browserFirst, setBrowserFirst] = useState(false);
  const [browserHeadful, setBrowserHeadful] = useState(false);
  const [browserEngine, setBrowserEngine] = useState("auto");
  const [browserHumanize, setBrowserHumanize] = useState(true);
  const [apiToken, setApiToken] = useState("");
  const [grabbing, setGrabbing] = useState(false);
  const [stoppingGrab, setStoppingGrab] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [installingHarvester, setInstallingHarvester] = useState(false);
  const [installingCamoufox, setInstallingCamoufox] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [busy, setBusy] = useState<Section | null>(null);

  useEffect(() => {
    api.getSettings().then(hydrate);
  }, []);

  function hydrate(s: Settings) {
    setSettings(s);
    setChatId(s.telegram_chat_id);
    setTgEnabled(s.telegram_enabled);
    setEmailEnabled(s.email_enabled);
    setSmtpHost(s.smtp_host);
    setSmtpPort(s.smtp_port);
    setSmtpUser(s.smtp_user);
    setEmailFrom(s.email_from);
    setEmailTo(s.email_to);
    setImapHost(s.imap_host);
    setImapPort(s.imap_port);
    setImapUser(s.imap_user);
    setAutoImport(s.email_import_auto_scan ?? false);
    setAutoImportHours(s.email_import_auto_scan_interval_hours ?? 24);
    setIntervalMin(s.scan_interval_minutes);
    setScanPaused(s.scanning_paused ?? false);
    setHealthAfter(s.health_alert_after_failures);
    setKeywords(s.excluded_keywords.join(", "));
    setMatchEnabled(s.match_score_enabled ?? false);
    setDreamMaxPrice(s.dream_max_price ?? 0);
    setDreamMinRooms(s.dream_min_rooms ?? 0);
    setDreamMinSqm(s.dream_min_sqm ?? 0);
    setDreamMinFloor(s.dream_min_floor ?? 0);
    setDreamKeywords((s.dream_keywords ?? []).join(", "));
    setDreamZones((s.dream_zones ?? []).join(", "));
    setNlBackend(s.nl_parser_backend || "deterministic");
    setLlmBaseUrl(s.llm_base_url || "");
    setLlmModel(s.llm_model || "");
    setProxyUrl(s.proxy_url || "");
    setProxyUrls((s.proxy_urls ?? []).join("\n"));
    setScrapeApiProvider(s.scrape_api_provider || "scrapfly");
    setScrapeApiMode(s.scrape_api_mode || "fallback");
    setAutoRefresh(s.datadome_auto_refresh ?? false);
    setBrowserFirst(s.availability_browser_first ?? false);
    setBrowserHeadful(s.availability_browser_headful ?? false);
    setBrowserEngine(s.browser_engine ?? "auto");
    setBrowserHumanize(s.browser_humanize ?? true);
    setApiToken(s.api_auth_token ?? "");
    // Secrets are write-only: the server never returns them, so the inputs go
    // back to their "already saved" placeholder rather than showing stale dots.
    setToken("");
    setSmtpPassword("");
    setImapPassword("");
    setDatadomeCookie("");
    setScrapeApiKey("");
    setLlmApiKey("");
  }

  /** Persists the form and refreshes local state from the server's answer. */
  async function persist() {
    const payload: Partial<Settings> = {
      telegram_chat_id: chatId,
      telegram_enabled: tgEnabled,
      email_enabled: emailEnabled,
      smtp_host: smtpHost,
      smtp_port: smtpPort,
      smtp_user: smtpUser,
      email_from: emailFrom,
      email_to: emailTo,
      imap_host: imapHost,
      imap_port: imapPort,
      imap_user: imapUser,
      email_import_auto_scan: autoImport,
      email_import_auto_scan_interval_hours: autoImportHours,
      scan_interval_minutes: interval,
      scanning_paused: scanPaused,
      health_alert_after_failures: healthAfter,
      excluded_keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
      match_score_enabled: matchEnabled,
      dream_max_price: dreamMaxPrice,
      dream_min_rooms: dreamMinRooms,
      dream_min_sqm: dreamMinSqm,
      dream_min_floor: dreamMinFloor,
      dream_keywords: dreamKeywords.split(",").map((k) => k.trim()).filter(Boolean),
      dream_zones: dreamZones.split(",").map((k) => k.trim()).filter(Boolean),
      nl_parser_backend: nlBackend,
      llm_base_url: llmBaseUrl,
      llm_model: llmModel,
      proxy_url: proxyUrl,
      proxy_urls: proxyUrls.split("\n").map((u) => u.trim()).filter(Boolean),
      scrape_api_provider: scrapeApiProvider,
      scrape_api_mode: scrapeApiMode,
      datadome_auto_refresh: autoRefresh,
      availability_browser_first: browserFirst,
      availability_browser_headful: browserHeadful,
      browser_engine: browserEngine,
      browser_humanize: browserHumanize,
      api_auth_token: apiToken,
    };
    // Keep this browser's stored token in step with the field, so enabling auth
    // does not lock out the very next request (and clearing it removes the token).
    if (apiToken.trim()) authToken.set(apiToken.trim());
    else authToken.clear();
    // An empty secret field means "keep the stored one", never "erase it".
    // Pasted app passwords keep their display spaces; save_settings strips them.
    if (token.trim()) payload.telegram_bot_token = token.trim();
    if (smtpPassword.trim()) payload.smtp_password = smtpPassword;
    if (imapPassword.trim()) payload.imap_password = imapPassword;
    if (datadomeCookie.trim()) payload.datadome_cookie = datadomeCookie;
    if (scrapeApiKey.trim()) payload.scrape_api_key = scrapeApiKey.trim();
    if (llmApiKey.trim()) payload.llm_api_key = llmApiKey.trim();
    hydrate(await api.updateSettings(payload));
  }

  async function save() {
    setBusy("global");
    setFeedback(null);
    try {
      await persist();
      setFeedback({ where: "global", ok: true, text: t("settings.saved") });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  /**
   * The test endpoints read the *saved* settings, not the form. Testing without
   * saving first silently exercised the previous credentials — the single most
   * confusing thing about this dialog — so every test button saves first.
   */
  async function saveAndTest(
    where: Section,
    test: () => Promise<unknown>,
    describe: (result: unknown) => string,
  ) {
    setBusy(where);
    setFeedback(null);
    try {
      await persist();
    } catch (e) {
      setFeedback({ where, ok: false, text: t("settings.saveFailed", { error: errorText(e) }) });
      setBusy(null);
      return;
    }
    try {
      setFeedback({ where, ok: true, text: describe(await test()) });
    } catch (e) {
      setFeedback({ where, ok: false, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  /** Opens a local browser to grab a fresh cookie. Headful on the server side,
   * so a CAPTCHA (if any) can be solved once — hence the "a window may open"
   * hint. Re-hydrates so the saved-timestamp and placeholder update. */
  async function grabCookie() {
    setGrabbing(true);
    setStoppingGrab(false);
    setFeedback(null);
    try {
      const r = await api.datadomeRefresh("immobiliare");
      hydrate(await api.getSettings());
      setFeedback({ where: "global", ok: true,
        text: t("settings.cookieGrabbed", { preview: r.cookie_preview }) });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setGrabbing(false);
      setStoppingGrab(false);
    }
  }

  // Not every block page this meets is a solvable CAPTCHA -- a hard "access
  // restricted" wall with no widget otherwise leaves the visible browser
  // stuck open for the full headful timeout with nothing to click. This asks
  // the running grab to stop at its next poll (a few seconds), same as the
  // availability check's Stop button.
  function stopGrabbingCookie() {
    setStoppingGrab(true);
    api.cancelDatadomeRefresh().catch(() => {});
  }

  /** Restart the backend and wait for it to come back, then reload the page so
   *  the whole UI is talking to the fresh process. Used after pulling a code
   *  update so the user need not hunt for the terminal window. */
  async function restartBackend() {
    if (!window.confirm(t("settings.restartConfirm"))) return;
    setRestarting(true);
    setFeedback(null);
    try {
      await api.restartBackend();
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      // A 404/405 means THIS backend predates the restart route, so it cannot
      // restart itself — the classic bootstrap trap. Say so plainly instead of
      // polling (the process never went down) and pretending it worked.
      if (/Method Not Allowed|Not Found|Error 40[45]/i.test(raw)) {
        setRestarting(false);
        setFeedback({ where: "global", ok: false, text: t("settings.restartTooOld") });
        return;
      }
      // Otherwise the socket dropped as the process went down — that is the
      // expected path; the poll below is the real "did it come back?" signal.
    }
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    await sleep(1500); // give it a moment to actually go down first
    const deadline = Date.now() + 40000;
    while (Date.now() < deadline) {
      try {
        await api.getScanStatus();
        window.location.reload();
        return;
      } catch {
        await sleep(1000);
      }
    }
    setRestarting(false);
    setFeedback({ where: "global", ok: false, text: t("settings.restartNoReturn") });
  }

  async function installHarvester() {
    setInstallingHarvester(true);
    setFeedback(null);
    try {
      const r = await api.installHarvester();
      hydrate(await api.getSettings());
      setFeedback({ where: "global", ok: true,
        text: r.message || t("settings.harvesterInstalledMsg") });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setInstallingHarvester(false);
    }
  }

  async function installCamoufox() {
    setInstallingCamoufox(true);
    setFeedback(null);
    try {
      const r = await api.installCamoufox();
      hydrate(await api.getSettings());
      setFeedback({ where: "global", ok: true,
        text: r.message || t("settings.camoufoxInstalledMsg") });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setInstallingCamoufox(false);
    }
  }

  /** Irreversible data reset. Confirmed in the browser (a second time for the
   * factory wipe), then the page reloads so the dashboard reflects the change. */
  async function runReset(
    scope: "email-import" | "dashboard" | "pricing-snapshots" | "factory",
    confirmText: string,
    doubleConfirm = false,
  ) {
    if (!window.confirm(confirmText)) return;
    if (doubleConfirm && !window.confirm(t("settings.lastChance"))) return;
    setBusy("data");
    setFeedback(null);
    try {
      const r = await api.resetData(scope);
      const removed = Object.entries(r.deleted)
        .map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ");
      setFeedback({
        where: "data",
        ok: true,
        text: r.backup
          ? t("settings.resetDoneBackup", {
              removed: removed || t("settings.resetNothing"),
              backup: r.backup,
            })
          : t("settings.resetDone", { removed: removed || t("settings.resetNothing") }),
      });
      setTimeout(() => window.location.reload(), 1600);
    } catch (e) {
      setFeedback({ where: "data", ok: false, text: errorText(e) });
      setBusy(null);
    }
  }

  function errorText(e: unknown) {
    const raw = e instanceof Error ? e.message : String(e);
    // Providers answer with protocol jargon; translate the two that a user can
    // actually act on, and pass everything else through untouched.
    if (/AUTHENTICATIONFAILED|Username and Password not accepted|535/i.test(raw)) {
      return translateCurrent("settings.errCredentials", { error: raw });
    }
    if (/timed out|timeout|Connection refused|getaddrinfo|Name or service not known/i.test(raw)) {
      return translateCurrent("settings.errNetwork", { error: raw });
    }
    return raw;
  }

  function Result({ where }: { where: Section }) {
    if (!feedback || feedback.where !== where) return null;
    return (
      <p role="status"
        className={`text-sm mt-3 rounded-lg px-3 py-2 ${feedback.ok
          ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : "bg-rose-500/10 text-rose-700 dark:text-rose-300"}`}>
        {feedback.ok ? "✅ " : "❌ "}{feedback.text}
      </p>
    );
  }

  if (!settings) return null;

  const anyBusy = busy !== null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/50 dark:bg-black/70 backdrop-blur-sm"
      onClick={onClose}>
      {/* dvh: `vh` on mobile spans behind the address bar, hiding the footer
          buttons ("Save settings") below the fold with no way to scroll to them */}
      <div className="glass rounded-2xl max-w-lg w-full p-4 sm:p-6 max-h-[90dvh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold">{t("settings.title")}</h2>
          <button className="btn-ghost" aria-label={t("common.close")} onClick={onClose}>✕</button>
        </div>

        <p className="text-xs t-dim mb-5">{t("settings.testNote")}</p>

        <h3 className="font-semibold text-sm uppercase t-muted mb-2">
          {t("settings.telegramTitle")}
        </h3>
        <HelpSteps
          summary={t("settings.telegramHelp")}
          steps={[
            t("settings.tgStep1"),
            t("settings.tgStep2"),
            t("settings.tgStep3"),
            t("settings.tgStep4"),
            t("settings.tgStep5"),
            t("settings.tgStep6"),
          ]}
        />
        <div className="space-y-3">
          <div>
            <input className="input w-full" type="password"
              placeholder={t(settings.telegram_token_set ? "settings.tokenSaved" : "settings.tokenPlaceholder")}
              value={token} onChange={(e) => setToken(e.target.value)} />
            <div className="mt-1">
              <SecretStatus set={settings.telegram_token_set} dirty={!!token.trim()} />
            </div>
          </div>
          <input className="input w-full" placeholder={t("settings.chatIdPlaceholder")}
            value={chatId} onChange={(e) => setChatId(e.target.value)} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={tgEnabled}
                onChange={(e) => setTgEnabled(e.target.checked)} />
              {t("settings.enableTelegram")}
            </label>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("telegram", api.telegramTest,
                () => t("settings.telegramTestSent"))}>
              {busy === "telegram" ? t("settings.sending") : t("settings.saveAndTest")}
            </button>
          </div>
          <Result where="telegram" />
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.emailTitle")}
        </h3>
        <HelpSteps
          summary={t("settings.emailHelp")}
          steps={[
            t("settings.emStep1"),
            <>
              {t("settings.emStep2a")}
              <Link href="https://myaccount.google.com/signinoptions/twosv">
                {t("settings.emStep2Link")}
              </Link>
              {t("settings.emStep2b")}
            </>,
            <>
              {t("settings.emStep3a")}
              <Link href="https://myaccount.google.com/apppasswords">
                myaccount.google.com/apppasswords
              </Link>
              {t("settings.emStep3b")}
            </>,
            t("settings.emStep4"),
            t("settings.emStep5"),
          ]}
        />
        <div className="space-y-3">
          {/* host and port share a row only when there is room for both: at
              phone width a 1/3-wide host field cannot show its own hostname */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className="input w-full sm:col-span-2" placeholder={t("settings.smtpHost")}
              value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
            <input className="input w-full" type="number" placeholder="587"
              title={t("settings.smtpPortTitle")}
              value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder={t("settings.smtpUser")}
              value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} />
            <div>
              <input className="input w-full" type="password"
                placeholder={t(settings.smtp_password_set ? "settings.passwordSaved" : "settings.appPassword")}
                value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.smtp_password_set} dirty={!!smtpPassword.trim()} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder={t("settings.emailFrom")}
              value={emailFrom} onChange={(e) => setEmailFrom(e.target.value)} />
            <input className="input w-full" placeholder={t("settings.emailTo")}
              value={emailTo} onChange={(e) => setEmailTo(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={emailEnabled}
                onChange={(e) => setEmailEnabled(e.target.checked)} />
              {t("settings.enableEmail")}
            </label>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("email", api.emailTest,
                () => t("settings.emailTestSent", {
                  to: emailTo || t("settings.theRecipient"),
                }))}>
              {busy === "email" ? t("settings.sending") : t("settings.saveAndTest")}
            </button>
          </div>
          <Result where="email" />
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.imapTitle")}
        </h3>
        <HelpSteps
          summary={t("settings.imapHelp")}
          steps={[
            t("settings.imStep1"),
            t("settings.imStep2"),
            t("settings.imStep3"),
            t("settings.imStep4"),
            t("settings.imStep5"),
          ]}
        />
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className="input w-full sm:col-span-2" placeholder={t("settings.imapHost")}
              value={imapHost} onChange={(e) => setImapHost(e.target.value)} />
            <input className="input w-full" type="number" placeholder="993"
              title={t("settings.imapPortTitle")}
              value={imapPort} onChange={(e) => setImapPort(Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder={t("settings.imapUser")}
              value={imapUser} onChange={(e) => setImapUser(e.target.value)} />
            <div>
              <input className="input w-full" type="password"
                placeholder={t(settings.imap_password_set ? "settings.passwordSaved" : "settings.appPassword")}
                value={imapPassword} onChange={(e) => setImapPassword(e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.imap_password_set} dirty={!!imapPassword.trim()} />
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs t-dim">{t("settings.readOnlyNote")}</p>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("imap", api.imapTest,
                (r) => (r as { detail: string }).detail)}>
              {busy === "imap" ? t("settings.connecting") : t("settings.saveAndTestConnection")}
            </button>
          </div>
          <Result where="imap" />
          <div className="pt-1">
            <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
              <input type="checkbox" checked={autoImport}
                onChange={(e) => setAutoImport(e.target.checked)} />
              {t("settings.autoImport")}
            </label>
            {autoImport && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center mt-2">
                <label className="text-xs t-muted" htmlFor="import-interval">
                  {t("settings.rescanFrequency")}
                </label>
                <select id="import-interval" className="input w-full"
                  value={autoImportHours}
                  onChange={(e) => setAutoImportHours(Number(e.target.value))}>
                  <option value={6}>{t("settings.every6h")}</option>
                  <option value={12}>{t("settings.every12h")}</option>
                  <option value={24}>{t("settings.onceADay")}</option>
                  <option value={72}>{t("settings.every3d")}</option>
                  <option value={168}>{t("settings.onceAWeek")}</option>
                </select>
              </div>
            )}
            <p className="text-xs t-dim mt-1">{t("settings.autoImportNote")}</p>
          </div>
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.scanTitle")}
        </h3>
        <label className="text-xs t-muted" htmlFor="scan-interval">{t("settings.frequency")}</label>
        <select id="scan-interval" className="input w-full mt-1" value={interval}
          onChange={(e) => setIntervalMin(Number(e.target.value))}>
          <option value={30}>{t("settings.every30m")}</option>
          <option value={60}>{t("settings.everyHour")}</option>
          <option value={120}>{t("settings.every2h")}</option>
          <option value={240}>{t("settings.every4h")}</option>
          <option value={480}>{t("settings.every8h")}</option>
        </select>

        <label className="flex items-start gap-2 mt-3 cursor-pointer">
          <input type="checkbox" checked={scanPaused} className="mt-0.5"
            onChange={(e) => setScanPaused(e.target.checked)} />
          <span className="text-sm">
            {t("settings.pauseScans")}
            <span className="block text-xs t-dim">{t("settings.pauseScansNote")}</span>
          </span>
        </label>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.healthTitle")}
        </h3>
        <p className="text-xs t-dim mb-2">{t("settings.healthNote")}</p>
        <label className="text-xs t-muted" htmlFor="health-after">
          {t("settings.alertAfter")}
        </label>
        <select id="health-after" className="input w-full mt-1" value={healthAfter}
          onChange={(e) => setHealthAfter(Number(e.target.value))}>
          <option value={0}>{t("settings.neverDisabled")}</option>
          {[2, 3, 5, 10].map((n) => (
            <option key={n} value={n}>{t("settings.nFailures", { count: n })}</option>
          ))}
        </select>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.keywordsTitle")}
        </h3>
        <p className="text-xs t-dim mb-2">{t("settings.keywordsNote")}</p>
        <textarea className="input w-full h-20 resize-none"
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.matchTitle")}
        </h3>
        <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
          <input type="checkbox" checked={matchEnabled}
            onChange={(e) => setMatchEnabled(e.target.checked)} />
          {t("settings.matchEnable")}
        </label>
        <p className="text-xs t-dim mt-1 mb-2">{t("settings.matchNote")}</p>
        {matchEnabled && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <label className="text-xs t-muted col-span-2 sm:col-span-1">
                {t("settings.dreamMaxPrice")}
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMaxPrice}
                  onChange={(e) => setDreamMaxPrice(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                {t("settings.dreamMinRooms")}
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinRooms}
                  onChange={(e) => setDreamMinRooms(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                {t("settings.dreamMinSqm")}
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinSqm}
                  onChange={(e) => setDreamMinSqm(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                {t("settings.dreamMinFloor")}
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinFloor}
                  onChange={(e) => setDreamMinFloor(Number(e.target.value))} />
              </label>
            </div>
            <div>
              <label className="text-xs t-muted block mb-1">
                {t("settings.dreamFeatures")}
              </label>
              <input className="input w-full" value={dreamKeywords}
                onChange={(e) => setDreamKeywords(e.target.value)} />
            </div>
            <div>
              <label className="text-xs t-muted block mb-1">
                {t("settings.dreamZones")}
              </label>
              <input className="input w-full" value={dreamZones}
                onChange={(e) => setDreamZones(e.target.value)} />
            </div>
          </div>
        )}

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.assistantTitle")}
        </h3>
        <p className="text-xs t-dim mb-2">{t("settings.assistantNote")}</p>
        <select className="input w-full" value={nlBackend}
          onChange={(e) => setNlBackend(e.target.value)}>
          <option value="deterministic">{t("settings.backendBuiltin")}</option>
          <option value="llm">{t("settings.backendLlm")}</option>
        </select>
        {nlBackend === "llm" && (
          <div className="space-y-2 mt-2">
            <p className="text-xs t-dim">
              {t("settings.llmHintA")}
              <Link href="https://ollama.com">Ollama</Link>
              {t("settings.llmHintB")}
              <code className="px-1 rounded bg-black/10 dark:bg-white/10 select-all">http://localhost:11434/v1</code>
              {t("settings.llmHintC")}
              <code className="px-1 rounded bg-black/10 dark:bg-white/10">llama3.1</code>
              {t("settings.llmHintD")}
            </p>
            <input className="input w-full" placeholder={t("settings.llmBaseUrl")}
              value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input className="input w-full" placeholder={t("settings.llmModel")}
                value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
              <div>
                <input className="input w-full" type="password"
                  placeholder={t(settings.llm_api_key_set ? "settings.llmKeySaved" : "settings.llmKeyPlaceholder")}
                  value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} />
                <div className="mt-1">
                  <SecretStatus set={settings.llm_api_key_set} dirty={!!llmApiKey.trim()} />
                </div>
              </div>
            </div>
          </div>
        )}

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.scrapingTitle")}
        </h3>
        <HelpSteps
          summary={t("settings.scrapingHelp")}
          steps={[
            t("settings.ddStep1"),
            t("settings.ddStep2"),
            <>
              {t("settings.ddStep3Intro")}
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li>{t("settings.ddStep3a")}</li>
                <li>{t("settings.ddStep3b")}</li>
                <li>{t("settings.ddStep3c")}</li>
                <li>{t("settings.ddStep3d")}</li>
              </ul>
            </>
          ]}
        />
        <div className="space-y-3">
          <div>
            <label className="text-xs t-muted block mb-1">{t("settings.proxyUrl")}</label>
            <input className="input w-full" placeholder={t("settings.proxyUrlPlaceholder")}
              value={proxyUrl} onChange={(e) => setProxyUrl(e.target.value)} />
          </div>
          <div>
            <label className="text-xs t-muted block mb-1">{t("settings.proxyPool")}</label>
            <textarea className="input w-full font-mono text-xs" rows={3}
              placeholder={"http://user:pass@proxy1:8000\nhttp://user:pass@proxy2:8000"}
              value={proxyUrls} onChange={(e) => setProxyUrls(e.target.value)} />
            <p className="text-xs t-dim mt-1">{t("settings.proxyPoolNote")}</p>
          </div>
          <div className="rounded-xl panel p-3 space-y-2">
            <p className="text-xs font-medium t-body">{t("settings.scrapeApiTitle")}</p>
            <p className="text-xs t-dim">{t("settings.scrapeApiNote")}</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <select className="input w-full" value={scrapeApiProvider}
                onChange={(e) => setScrapeApiProvider(e.target.value)}>
                <option value="scrapfly">Scrapfly</option>
                <option value="scraperapi">ScraperAPI</option>
                <option value="zyte">Zyte</option>
              </select>
              <div className="sm:col-span-2">
                <input className="input w-full" type="password"
                  placeholder={t(settings.scrape_api_key_set ? "settings.scrapeKeySaved" : "settings.scrapeKeyPlaceholder")}
                  value={scrapeApiKey} onChange={(e) => setScrapeApiKey(e.target.value)} />
                <div className="mt-1">
                  <SecretStatus set={settings.scrape_api_key_set} dirty={!!scrapeApiKey.trim()} />
                </div>
              </div>
            </div>
            <div>
              <label className="text-xs t-muted block mb-1">{t("settings.whenToUse")}</label>
              <select className="input w-full sm:w-auto" value={scrapeApiMode}
                onChange={(e) => setScrapeApiMode(e.target.value)}>
                <option value="fallback">{t("settings.modeFallback")}</option>
                <option value="always">{t("settings.modeAlways")}</option>
              </select>
              <p className="text-xs t-dim mt-1">{t("settings.modeNote")}</p>
            </div>
          </div>
          <div>
            <label className="text-xs t-muted block mb-1">{t("settings.cookieLabel")}</label>
            <input className="input w-full" type="password"
              placeholder={t(settings.datadome_cookie_set ? "settings.cookieSaved" : "settings.cookiePlaceholder")}
              value={datadomeCookie} onChange={(e) => setDatadomeCookie(e.target.value)} />
            <div className="mt-1">
              <SecretStatus set={settings.datadome_cookie_set}
                since={settings.datadome_cookie_updated_at}
                dirty={!!datadomeCookie.trim()} />
            </div>
          </div>

          {/* Automatic harvesting: only offered when Playwright is installed,
              otherwise the button would just error. The manual paste above
              always stays as the zero-dependency fallback. */}
          <div className="rounded-xl panel p-3 space-y-2">
            <p className="text-xs font-medium t-body">{t("settings.harvestTitle")}</p>
            {settings.datadome_harvester_available ? (
              <>
                <p className="text-xs t-dim">{t("settings.harvestNote")}</p>
                <div className="flex items-center gap-2">
                  <button className="btn-ghost" onClick={grabCookie}
                    disabled={grabbing || anyBusy}>
                    {grabbing ? t("settings.openingBrowser") : t("settings.grabCookie")}
                  </button>
                  {grabbing && (
                    <button className="btn-ghost" onClick={stopGrabbingCookie}
                      disabled={stoppingGrab}>
                      {stoppingGrab ? t("app.stopping") : t("app.stop")}
                    </button>
                  )}
                </div>
                <label className="flex items-center gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)} />
                  {t("settings.autoRefreshCookie")}
                </label>
                <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={browserFirst} className="mt-0.5"
                    onChange={(e) => setBrowserFirst(e.target.checked)} />
                  <span>{t("settings.browserFirst")}</span>
                </label>
                <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={browserHeadful} className="mt-0.5"
                    onChange={(e) => setBrowserHeadful(e.target.checked)} />
                  <span>{t("settings.browserHeadful")}</span>
                </label>

                <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={browserHumanize} className="mt-0.5"
                    onChange={(e) => setBrowserHumanize(e.target.checked)} />
                  <span>{t("settings.browserHumanize")}</span>
                </label>

                <div className="pt-2 mt-1 border-t border-slate-200/50 dark:border-slate-700/50 space-y-1.5">
                  <label className="flex items-center gap-2 text-xs t-body">
                    <span className="whitespace-nowrap">{t("settings.browserEngine")}</span>
                    <select className="input py-1 w-full sm:w-auto"
                      value={browserEngine}
                      onChange={(e) => setBrowserEngine(e.target.value)}>
                      <option value="auto">{t("settings.engineAuto")}</option>
                      <option value="camoufox">{t("settings.engineCamoufox")}</option>
                      <option value="chromium">{t("settings.engineChromium")}</option>
                    </select>
                  </label>
                  <p className="text-[11px] t-muted">
                    {t("settings.camoufoxNote")}{" "}
                    {t(settings.camoufox_available
                      ? "settings.camoufoxInstalled"
                      : "settings.camoufoxMissing")}
                  </p>
                  {!settings.camoufox_available && (
                    <button className="btn-ghost text-xs w-full sm:w-auto" onClick={installCamoufox}
                      disabled={installingCamoufox || anyBusy}>
                      {installingCamoufox
                        ? t("settings.installingCamoufox")
                        : t("settings.installCamoufox")}
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-2.5 pt-1">
                <p className="text-xs t-dim">{t("settings.harvesterMissing")}</p>
                <button className="btn-ghost text-xs w-full sm:w-auto" onClick={installHarvester}
                  disabled={installingHarvester || anyBusy}>
                  {installingHarvester
                    ? t("settings.installingHarvester")
                    : t("settings.installHarvester")}
                </button>
                <p className="text-[11px] t-muted pt-1">
                  {t("settings.manualInstall")}
                  <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10 select-all">
                    backend\.venv\Scripts\pip install playwright &amp;&amp; backend\.venv\Scripts\playwright install chromium
                  </code>
                </p>
              </div>
            )}
          </div>
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.apiTokenTitle")}
        </h3>
        <p className="text-xs t-dim mb-2">{t("settings.apiTokenNote")}</p>
        <input className="input w-full" type="password"
          placeholder={t("settings.apiTokenPlaceholder")}
          value={apiToken} onChange={(e) => setApiToken(e.target.value)} />
        <div className="mt-1">
          <SecretStatus
            set={!!(settings.api_auth_token ?? "")}
            dirty={apiToken !== (settings.api_auth_token ?? "")} />
        </div>

        <Result where="global" />

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          {t("settings.backendTitle")}
        </h3>
        <p className="text-xs t-dim mb-2">{t("settings.backendNote")}</p>
        <button className="btn-ghost w-full sm:w-auto" onClick={restartBackend}
          disabled={restarting || anyBusy}>
          {restarting ? t("settings.restarting") : t("settings.restart")}
        </button>

        <div className="mt-8 pt-5 border-t border-rose-300/40 dark:border-rose-800/40">
          <h3 className="font-semibold text-sm uppercase text-rose-600 dark:text-rose-400 mb-1">
            {t("settings.dataTitle")}
          </h3>
          <p className="text-xs t-dim mb-3">{t("settings.dataNote")}</p>
          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">{t("settings.resetImportsName")}</span>
                {t("settings.resetImportsBody")}
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("email-import", t("settings.resetImportsConfirm"))}>
                {t("settings.resetImportsButton")}
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">{t("settings.clearDashboardName")}</span>
                {t("settings.clearDashboardBody")}
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("dashboard", t("settings.clearDashboardConfirm"))}>
                {t("settings.clearDashboardButton")}
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">{t("settings.clearTrendsName")}</span>
                {t("settings.clearTrendsBody")}
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("pricing-snapshots", t("settings.clearTrendsConfirm"))}>
                {t("settings.clearTrendsButton")}
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">{t("settings.factoryName")}</span>
                {t("settings.factoryBody")}
              </div>
              <button className="btn-ghost w-full sm:w-auto text-white bg-rose-600 hover:bg-rose-700 border-rose-600"
                disabled={anyBusy}
                onClick={() => runReset("factory", t("settings.factoryConfirm"), true)}>
                {t("settings.factoryButton")}
              </button>
            </div>
          </div>
          <Result where="data" />
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button className="btn-ghost" onClick={onClose}>{t("common.close")}</button>
          <button className="btn-primary" onClick={save} disabled={anyBusy}>
            {busy === "global" ? t("common.saving") : t("settings.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
