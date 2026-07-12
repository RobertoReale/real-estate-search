import { useEffect, useState, type ReactNode } from "react";
import { api } from "../services/api";
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

export default function SettingsModal({ onClose }: Props) {
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
  const [proxyUrl, setProxyUrl] = useState("");
  const [datadomeCookie, setDatadomeCookie] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [browserFirst, setBrowserFirst] = useState(false);
  const [browserHeadful, setBrowserHeadful] = useState(false);
  const [browserEngine, setBrowserEngine] = useState("auto");
  const [grabbing, setGrabbing] = useState(false);
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
    setProxyUrl(s.proxy_url || "");
    setAutoRefresh(s.datadome_auto_refresh ?? false);
    setBrowserFirst(s.availability_browser_first ?? false);
    setBrowserHeadful(s.availability_browser_headful ?? false);
    setBrowserEngine(s.browser_engine ?? "auto");
    // Secrets are write-only: the server never returns them, so the inputs go
    // back to their "already saved" placeholder rather than showing stale dots.
    setToken("");
    setSmtpPassword("");
    setImapPassword("");
    setDatadomeCookie("");
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
      proxy_url: proxyUrl,
      datadome_auto_refresh: autoRefresh,
      availability_browser_first: browserFirst,
      availability_browser_headful: browserHeadful,
      browser_engine: browserEngine,
    };
    // An empty secret field means "keep the stored one", never "erase it".
    // Pasted app passwords keep their display spaces; save_settings strips them.
    if (token.trim()) payload.telegram_bot_token = token.trim();
    if (smtpPassword.trim()) payload.smtp_password = smtpPassword;
    if (imapPassword.trim()) payload.imap_password = imapPassword;
    if (datadomeCookie.trim()) payload.datadome_cookie = datadomeCookie;
    hydrate(await api.updateSettings(payload));
  }

  async function save() {
    setBusy("global");
    setFeedback(null);
    try {
      await persist();
      setFeedback({ where: "global", ok: true, text: "Settings saved." });
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
      setFeedback({ where, ok: false, text: `Could not save settings: ${errorText(e)}` });
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
    setFeedback(null);
    try {
      const r = await api.datadomeRefresh("immobiliare");
      hydrate(await api.getSettings());
      setFeedback({ where: "global", ok: true,
        text: `Fresh DataDome cookie saved (${r.cookie_preview}).` });
    } catch (e) {
      setFeedback({ where: "global", ok: false, text: errorText(e) });
    } finally {
      setGrabbing(false);
    }
  }

  async function installHarvester() {
    setInstallingHarvester(true);
    setFeedback(null);
    try {
      const r = await api.installHarvester();
      hydrate(await api.getSettings());
      setFeedback({ where: "global", ok: true,
        text: r.message || "Playwright & Chromium installed successfully!" });
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
        text: r.message || "Camoufox installed successfully!" });
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
    if (doubleConfirm && !window.confirm(
      "Last chance: this erases everything and cannot be undone. Continue?")) return;
    setBusy("data");
    setFeedback(null);
    try {
      const r = await api.resetData(scope);
      const removed = Object.entries(r.deleted)
        .map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ");
      setFeedback({ where: "data", ok: true,
        text: `Done — removed ${removed || "nothing"}${r.backup ? ` · backup saved: ${r.backup}` : ""}. Reloading…` });
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
      return `${raw} — the credentials were refused. With Gmail you must use a 16-character App password, not your normal password.`;
    }
    if (/timed out|timeout|Connection refused|getaddrinfo|Name or service not known/i.test(raw)) {
      return `${raw} — could not reach the server. Check the host name and port.`;
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
          <h2 className="text-lg font-bold">⚙️ Settings</h2>
          <button className="btn-ghost" aria-label="Close" onClick={onClose}>✕</button>
        </div>

        <p className="text-xs t-dim mb-5">
          Each test button saves your changes first, so what it tests is exactly
          what you typed.
        </p>

        <h3 className="font-semibold text-sm uppercase t-muted mb-2">
          📨 Telegram notifications
        </h3>
        <HelpSteps
          summary="How do I set up Telegram? (step-by-step)"
          steps={[
            "Open Telegram and search for @BotFather.",
            'Send "/newbot" and follow the prompts; copy the token it gives you.',
            "Paste the token below.",
            "Search for your new bot by name and send it any message (this authorizes it to write to you).",
            "Get your Chat ID: message @userinfobot and copy the number it replies with.",
            'Paste the Chat ID below, tick "Enable", then press "Save & send test".',
          ]}
        />
        <div className="space-y-3">
          <input className="input w-full" type="password"
            placeholder={settings.telegram_token_set ? "Token already saved (leave empty to keep)" : "Bot token (from @BotFather)"}
            value={token} onChange={(e) => setToken(e.target.value)} />
          <input className="input w-full" placeholder="Chat ID (e.g. 123456789)"
            value={chatId} onChange={(e) => setChatId(e.target.value)} />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={tgEnabled}
                onChange={(e) => setTgEnabled(e.target.checked)} />
              Enable Telegram notifications
            </label>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("telegram", api.telegramTest,
                () => "Test message sent — check your Telegram chat.")}>
              {busy === "telegram" ? "Sending…" : "Save & send test"}
            </button>
          </div>
          <Result where="telegram" />
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          ✉️ Email notifications
        </h3>
        <HelpSteps
          summary="How do I set up Email alerts? (works with Gmail)"
          steps={[
            "For Gmail: host smtp.gmail.com, port 587, username = your Gmail address.",
            <>
              Gmail needs an <em>App password</em>, not your normal password. It
              only exists once 2-Step Verification is on, so{" "}
              <Link href="https://myaccount.google.com/signinoptions/twosv">turn that on first</Link>
              {" "}— until you do, the App passwords page will say it is not
              available for your account.
            </>,
            <>
              Then create one at{" "}
              <Link href="https://myaccount.google.com/apppasswords">myaccount.google.com/apppasswords</Link>
              {" "}and paste the 16 characters below (spaces are ignored).
            </>,
            "Recipient: the address where you want to receive alerts (it can be the same one).",
            'Tick "Enable", then press "Save & send test".',
          ]}
        />
        <div className="space-y-3">
          {/* host and port share a row only when there is room for both: at
              phone width a 1/3-wide host field cannot show its own hostname */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className="input w-full sm:col-span-2" placeholder="SMTP host (e.g. smtp.gmail.com)"
              value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
            <input className="input w-full" type="number" placeholder="587"
              title="Port (587 STARTTLS, 465 SSL)"
              value={smtpPort} onChange={(e) => setSmtpPort(Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder="SMTP username (email address)"
              value={smtpUser} onChange={(e) => setSmtpUser(e.target.value)} />
            <input className="input w-full" type="password"
              placeholder={settings.smtp_password_set ? "Password saved (leave empty to keep)" : "App password (16 characters)"}
              value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder="Sender (optional, defaults to username)"
              value={emailFrom} onChange={(e) => setEmailFrom(e.target.value)} />
            <input className="input w-full" placeholder="Recipient (you@example.com)"
              value={emailTo} onChange={(e) => setEmailTo(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={emailEnabled}
                onChange={(e) => setEmailEnabled(e.target.checked)} />
              Enable email notifications
            </label>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("email", api.emailTest,
                () => `Test email sent to ${emailTo || "the recipient"} — check your inbox (and the spam folder).`)}>
              {busy === "email" ? "Sending…" : "Save & send test"}
            </button>
          </div>
          <Result where="email" />
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          📥 Email inbox import (IMAP)
        </h3>
        <HelpSteps
          summary="What is this? How do I set it up? (works with Gmail)"
          steps={[
            "Lets the dashboard mine your own inbox for old Immobiliare.it / Idealista alert emails and import those listings for review.",
            "Strictly read-only: the app never modifies, marks or deletes your emails, and nothing appears in the dashboard until you accept it.",
            "For Gmail: host imap.gmail.com, port 993, username = your Gmail address.",
            "Password: the same 16-character App password as the email section above.",
            <>
              Press "Save &amp; test connection", then use the "📥 Import from
              email" panel in the dashboard.
            </>,
          ]}
        />
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <input className="input w-full sm:col-span-2" placeholder="IMAP host (e.g. imap.gmail.com)"
              value={imapHost} onChange={(e) => setImapHost(e.target.value)} />
            <input className="input w-full" type="number" placeholder="993"
              title="Port (993 SSL)"
              value={imapPort} onChange={(e) => setImapPort(Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input className="input w-full" placeholder="IMAP username (email address)"
              value={imapUser} onChange={(e) => setImapUser(e.target.value)} />
            <input className="input w-full" type="password"
              placeholder={settings.imap_password_set ? "Password saved (leave empty to keep)" : "App password (16 characters)"}
              value={imapPassword} onChange={(e) => setImapPassword(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs t-dim">
              Read-only access: your mailbox is never modified.
            </p>
            <button className="btn-ghost" disabled={anyBusy}
              onClick={() => saveAndTest("imap", api.imapTest,
                (r) => (r as { detail: string }).detail)}>
              {busy === "imap" ? "Connecting…" : "Save & test connection"}
            </button>
          </div>
          <Result where="imap" />
          <div className="pt-1">
            <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
              <input type="checkbox" checked={autoImport}
                onChange={(e) => setAutoImport(e.target.checked)} />
              Re-scan the inbox automatically for new listing emails
            </label>
            {autoImport && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 items-center mt-2">
                <label className="text-xs t-muted" htmlFor="import-interval">
                  Re-scan frequency
                </label>
                <select id="import-interval" className="input w-full"
                  value={autoImportHours}
                  onChange={(e) => setAutoImportHours(Number(e.target.value))}>
                  <option value={6}>Every 6 hours</option>
                  <option value={12}>Every 12 hours</option>
                  <option value={24}>Once a day</option>
                  <option value={72}>Every 3 days</option>
                  <option value={168}>Once a week</option>
                </select>
              </div>
            )}
            <p className="text-xs t-dim mt-1">
              New listings are staged silently in the "📥 Import from email"
              review queue — you are not notified, and nothing appears in the
              dashboard until you accept it.
            </p>
          </div>
        </div>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          🔄 Automatic scan
        </h3>
        <label className="text-xs t-muted" htmlFor="scan-interval">Frequency</label>
        <select id="scan-interval" className="input w-full mt-1" value={interval}
          onChange={(e) => setIntervalMin(Number(e.target.value))}>
          <option value={30}>Every 30 minutes</option>
          <option value={60}>Every hour</option>
          <option value={120}>Every 2 hours</option>
          <option value={240}>Every 4 hours</option>
          <option value={480}>Every 8 hours</option>
        </select>

        <label className="flex items-start gap-2 mt-3 cursor-pointer">
          <input type="checkbox" checked={scanPaused} className="mt-0.5"
            onChange={(e) => setScanPaused(e.target.checked)} />
          <span className="text-sm">
            Pause automatic scans
            <span className="block text-xs t-dim">
              Stops scheduled scans from touching the portals — useful for
              resting the connection while you are away. "Scan now" still works
              on demand.
            </span>
          </span>
        </label>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          🚨 Scraper health alerts
        </h3>
        <p className="text-xs t-dim mb-2">
          A broken scraper is silent: no listings looks exactly like a quiet
          market. Get notified when a search fails this many scans in a row.
          Portals block scrapers occasionally, so a value of 1 will cry wolf.
        </p>
        <label className="text-xs t-muted" htmlFor="health-after">
          Alert after
        </label>
        <select id="health-after" className="input w-full mt-1" value={healthAfter}
          onChange={(e) => setHealthAfter(Number(e.target.value))}>
          <option value={0}>Never (disabled)</option>
          <option value={2}>2 consecutive failures</option>
          <option value={3}>3 consecutive failures</option>
          <option value={5}>5 consecutive failures</option>
          <option value={10}>10 consecutive failures</option>
        </select>

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          🚫 Excluded keywords (global)
        </h3>
        <p className="text-xs t-dim mb-2">
          Listings containing these words are automatically discarded (whole
          words only, accents ignored). Separate with commas. Each search
          profile can add its own extra keywords on top of these.
        </p>
        <textarea className="input w-full h-20 resize-none"
          value={keywords} onChange={(e) => setKeywords(e.target.value)} />

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          🎯 Smart Match Score (dream home)
        </h3>
        <label className="flex items-center gap-2 text-xs t-body cursor-pointer">
          <input type="checkbox" checked={matchEnabled}
            onChange={(e) => setMatchEnabled(e.target.checked)} />
          Show a compatibility % on each card, scored against the wishes below
        </label>
        <p className="text-xs t-dim mt-1 mb-2">
          Every field is optional — leave a number at 0 to ignore it. Only the
          wishes you fill in count towards the score. Nothing leaves your PC.
        </p>
        {matchEnabled && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <label className="text-xs t-muted col-span-2 sm:col-span-1">
                Max price (€)
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMaxPrice}
                  onChange={(e) => setDreamMaxPrice(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                Min rooms
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinRooms}
                  onChange={(e) => setDreamMinRooms(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                Min sqm
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinSqm}
                  onChange={(e) => setDreamMinSqm(Number(e.target.value))} />
              </label>
              <label className="text-xs t-muted">
                Min floor
                <input className="input w-full mt-1" type="number" min={0}
                  value={dreamMinFloor}
                  onChange={(e) => setDreamMinFloor(Number(e.target.value))} />
              </label>
            </div>
            <div>
              <label className="text-xs t-muted block mb-1">
                Desired features (comma-separated, e.g. balcone, ascensore, terrazzo)
              </label>
              <input className="input w-full" value={dreamKeywords}
                onChange={(e) => setDreamKeywords(e.target.value)} />
            </div>
            <div>
              <label className="text-xs t-muted block mb-1">
                Preferred zones or cities (comma-separated)
              </label>
              <input className="input w-full" value={dreamZones}
                onChange={(e) => setDreamZones(e.target.value)} />
            </div>
          </div>
        )}

        <h3 className="font-semibold text-sm uppercase t-muted mt-6 mb-2">
          🛡️ Advanced Scraping & Bypass
        </h3>
        <HelpSteps
          summary="How to resolve DataDome blocks? (instructions)"
          steps={[
            "DataDome blocks raw HTTP requests to individual ad pages on your home IP.",
            "Option A: Set a Proxy URL (e.g. socks5://127.0.0.1:9050 for Tor, or an HTTP/HTTPS proxy) below to route scraper traffic.",
            <>
              Option B: Copy the <strong>datadome</strong> cookie value from your web browser:
              <ul className="list-disc list-inside ml-4 mt-1 space-y-1">
                <li>Open a portal ad page (e.g., Immobiliare.it) in Chrome/Firefox.</li>
                <li>Press F12, go to the <strong>Application</strong> (Chrome) or <strong>Storage</strong> (Firefox) tab.</li>
                <li>Under <strong>Cookies</strong>, select the portal domain, find <strong>datadome</strong>, and copy its value.</li>
                <li>Paste it in the Cookie field below. Note: it will expire after a few hours.</li>
              </ul>
            </>
          ]}
        />
        <div className="space-y-3">
          <div>
            <label className="text-xs t-muted block mb-1">Proxy URL (HTTP/HTTPS/SOCKS5)</label>
            <input className="input w-full" placeholder="e.g. socks5://127.0.0.1:9050"
              value={proxyUrl} onChange={(e) => setProxyUrl(e.target.value)} />
          </div>
          <div>
            <label className="text-xs t-muted block mb-1">DataDome Cookie</label>
            <input className="input w-full" type="password"
              placeholder={settings.datadome_cookie_set ? "Cookie already saved (leave empty to keep)" : "Paste datadome cookie value"}
              value={datadomeCookie} onChange={(e) => setDatadomeCookie(e.target.value)} />
            {settings.datadome_cookie_updated_at && (
              <p className="text-xs t-dim mt-1">
                Last refreshed:{" "}
                {new Date(settings.datadome_cookie_updated_at).toLocaleString("en-IE")}
              </p>
            )}
          </div>

          {/* Automatic harvesting: only offered when Playwright is installed,
              otherwise the button would just error. The manual paste above
              always stays as the zero-dependency fallback. */}
          <div className="rounded-xl panel p-3 space-y-2">
            <p className="text-xs font-medium t-body">
              🤖 Grab the cookie automatically
            </p>
            {settings.datadome_harvester_available ? (
              <>
                <p className="text-xs t-dim">
                  Opens a local browser, earns a fresh cookie, and saves it — no
                  copy/paste. A window may open: if the portal shows a CAPTCHA,
                  solve it once and it is remembered next time.
                </p>
                <button className="btn-ghost" onClick={grabCookie}
                  disabled={grabbing || anyBusy}>
                  {grabbing ? "Opening browser…" : "🔄 Grab a fresh cookie now"}
                </button>
                <label className="flex items-center gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={autoRefresh}
                    onChange={(e) => setAutoRefresh(e.target.checked)} />
                  Refresh the cookie automatically before each scan (headless)
                </label>
                <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={browserFirst} className="mt-0.5"
                    onChange={(e) => setBrowserFirst(e.target.checked)} />
                  <span>
                    Run the "still online?" check through the browser instead of
                    fast requests — slower per ad, but it holds a real cookie so
                    DataDome does not interrupt it with 403 blocks.
                  </span>
                </label>
                <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                  <input type="checkbox" checked={browserHeadful} className="mt-0.5"
                    onChange={(e) => setBrowserHeadful(e.target.checked)} />
                  <span>
                    Show the browser window during the check so you can solve a
                    CAPTCHA by hand if one appears — one solve unblocks the whole
                    run. Works best together with the option above. Ignored when
                    the app runs as a background Windows service.
                  </span>
                </label>

                <div className="pt-2 mt-1 border-t border-slate-200/50 dark:border-slate-700/50 space-y-1.5">
                  <label className="flex items-center gap-2 text-xs t-body">
                    <span className="whitespace-nowrap">Browser engine:</span>
                    <select className="input py-1 w-full sm:w-auto"
                      value={browserEngine}
                      onChange={(e) => setBrowserEngine(e.target.value)}>
                      <option value="auto">Auto (Camoufox if installed, else Chromium)</option>
                      <option value="camoufox">Camoufox (stealth Firefox)</option>
                      <option value="chromium">Chromium</option>
                    </select>
                  </label>
                  <p className="text-[11px] t-muted">
                    Camoufox is a stealth Firefox that hides the automation signals
                    DataDome looks for, so the check is challenged far less often.{" "}
                    {settings.camoufox_available
                      ? "Installed ✓"
                      : "Not installed — one-click adds it (~150 MB, one time):"}
                  </p>
                  {!settings.camoufox_available && (
                    <button className="btn-ghost text-xs w-full sm:w-auto" onClick={installCamoufox}
                      disabled={installingCamoufox || anyBusy}>
                      {installingCamoufox ? "⚡ Installing Camoufox (~1-3 min)…" : "⚡ One-Click Install Camoufox"}
                    </button>
                  )}
                </div>
              </>
            ) : (
              <div className="space-y-2.5 pt-1">
                <p className="text-xs t-dim">
                  Not installed yet in this Python environment. You can install Playwright and Chromium automatically with one click:
                </p>
                <button className="btn-ghost text-xs w-full sm:w-auto" onClick={installHarvester}
                  disabled={installingHarvester || anyBusy}>
                  {installingHarvester ? "⚡ Installing Playwright & Chromium (~1-2 min)…" : "⚡ One-Click Install Playwright & Chromium"}
                </button>
                <p className="text-[11px] t-muted pt-1">
                  Or install manually from terminal using `install-playwright.bat` inside the project folder, or run:{" "}
                  <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10 select-all">
                    backend\.venv\Scripts\pip install playwright &amp;&amp; backend\.venv\Scripts\playwright install chromium
                  </code>
                </p>
              </div>
            )}
          </div>
        </div>

        <Result where="global" />

        <div className="mt-8 pt-5 border-t border-rose-300/40 dark:border-rose-800/40">
          <h3 className="font-semibold text-sm uppercase text-rose-600 dark:text-rose-400 mb-1">
            🧹 Data management
          </h3>
          <p className="text-xs t-dim mb-3">
            Irreversible. Your notification and login settings are always kept.
          </p>
          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">Reset email imports</span> — clear
                every listing found in your inbox so you can import again from
                scratch (also forgets discarded ones).
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("email-import",
                  "Delete ALL imported email listings? You can re-run the inbox import afterwards.")}>
                Reset imports
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">Clear dashboard</span> — delete all
                found properties and price history. Your search profiles stay; the
                next scan rebuilds the grid silently.
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("dashboard",
                  "Delete ALL properties and their price history? Search profiles are kept and the next scan will rebuild the dashboard.")}>
                Clear dashboard
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">Clear price trends</span> — remove
                the daily median history behind the trend charts, without touching
                any listing.
              </div>
              <button className="btn-ghost w-full sm:w-auto text-rose-600 dark:text-rose-400"
                disabled={anyBusy}
                onClick={() => runReset("pricing-snapshots",
                  "Delete the stored price-trend history? The charts will start over from the next scan.")}>
                Clear trends
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <div className="flex-1 text-xs t-body">
                <span className="font-medium">Factory reset</span> — wipe
                everything (dashboard, profiles, imports, trends) back to a fresh
                install. A backup of the database is saved first.
              </div>
              <button className="btn-ghost w-full sm:w-auto text-white bg-rose-600 hover:bg-rose-700 border-rose-600"
                disabled={anyBusy}
                onClick={() => runReset("factory",
                  "Factory reset: this deletes the dashboard, ALL search profiles, imports and trends. A backup is saved first. Continue?",
                  true)}>
                Factory reset
              </button>
            </div>
          </div>
          <Result where="data" />
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button className="btn-ghost" onClick={onClose}>Close</button>
          <button className="btn-primary" onClick={save} disabled={anyBusy}>
            {busy === "global" ? "Saving…" : "Save settings"}
          </button>
        </div>
      </div>
    </div>
  );
}
