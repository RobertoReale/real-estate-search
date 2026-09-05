import { useState } from "react";
import { useT } from "../../i18n";
import {
  useCancelDatadomeRefresh, useDatadomeRefresh, useInstallBrowser,
} from "../../queries/settings";
import type { Settings } from "../../types";
import { useToasts } from "../Toast";
import { HelpSteps, Link, SecretStatus, SectionHeading } from "./controls";
import { Bypass, Credential, Harvester, Restart } from "../../ui/icons";
import { useSectionState, type Section, type SettingsShell } from "./state";

interface Values {
  proxyUrl: string;
  proxyUrls: string;
  apiProvider: string;
  apiKey: string;
  apiMode: string;
  idealistaKey: string;
  idealistaSecret: string;
  idealistaMaxPages: number;
  cookie: string;
  autoRefresh: boolean;
  browserFirst: boolean;
  browserHeadful: boolean;
  engine: string;
  humanize: boolean;
}

export function useScrapingSection(): Section<Values> {
  return useSectionState<Values>(
    {
      proxyUrl: "", proxyUrls: "", apiProvider: "scrapfly", apiKey: "",
      apiMode: "fallback", idealistaKey: "", idealistaSecret: "", idealistaMaxPages: 1,
      cookie: "", autoRefresh: false, browserFirst: false,
      browserHeadful: false, engine: "auto", humanize: true,
    },
    (s) => ({
      proxyUrl: s.proxy_url || "",
      proxyUrls: (s.proxy_urls ?? []).join("\n"),
      apiProvider: s.scrape_api_provider || "scrapfly",
      apiKey: "", // write-only
      apiMode: s.scrape_api_mode || "fallback",
      idealistaKey: "", // write-only
      idealistaSecret: "", // write-only
      idealistaMaxPages: s.idealista_api_max_pages ?? 1,
      cookie: "", // write-only
      autoRefresh: s.datadome_auto_refresh ?? false,
      browserFirst: s.availability_browser_first ?? false,
      browserHeadful: s.availability_browser_headful ?? false,
      engine: s.browser_engine ?? "auto",
      humanize: s.browser_humanize ?? true,
    }),
    (v) => {
      const p: Partial<Settings> = {
        proxy_url: v.proxyUrl,
        // One proxy per line, unlike the comma-separated keyword fields: a
        // proxy URL may legitimately contain a comma in its password.
        proxy_urls: v.proxyUrls.split("\n").map((u) => u.trim()).filter(Boolean),
        scrape_api_provider: v.apiProvider,
        scrape_api_mode: v.apiMode,
        // Each page is one metered request, and the backend refuses 0 — so a
        // cleared field means the conservative default, never "unlimited".
        idealista_api_max_pages: Math.max(1, v.idealistaMaxPages || 1),
        datadome_auto_refresh: v.autoRefresh,
        availability_browser_first: v.browserFirst,
        availability_browser_headful: v.browserHeadful,
        browser_engine: v.engine,
        browser_humanize: v.humanize,
      };
      if (v.apiKey.trim()) p.scrape_api_key = v.apiKey.trim();
      if (v.idealistaKey.trim()) p.idealista_api_key = v.idealistaKey.trim();
      if (v.idealistaSecret.trim()) p.idealista_api_secret = v.idealistaSecret.trim();
      if (v.cookie.trim()) p.datadome_cookie = v.cookie;
      return p;
    },
  );
}

export function ScrapingSection(
  { section, settings, shell }: { section: Section<Values>; settings: Settings; shell: SettingsShell },
) {
  const t = useT();
  const toasts = useToasts();
  const { values, set } = section;
  const [stoppingGrab, setStoppingGrab] = useState(false);
  const [installing, setInstalling] = useState<"harvester" | "camoufox" | null>(null);
  const grab = useDatadomeRefresh();
  const cancelGrab = useCancelDatadomeRefresh();
  const installBrowser = useInstallBrowser();
  const grabbing = grab.isPending;

  /** Opens a local browser to grab a fresh cookie. Headful on the server side,
   * so a CAPTCHA (if any) can be solved once — hence the "a window may open"
   * hint. Re-hydrates so the saved-timestamp and placeholder update. */
  async function grabCookie() {
    setStoppingGrab(false);
    shell.setFeedback(null);
    try {
      const r = await grab.mutateAsync("immobiliare");
      await shell.reload();
      shell.setFeedback({ where: "global",
        text: t("settings.cookieGrabbed", { preview: r.cookie_preview }) });
    } catch (e) {
      toasts.fail(e, { retry: () => grabCookie() });
    } finally {
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
    // best-effort: a refused cancel just leaves the grab running to its own end
    cancelGrab.mutate(undefined, { onError: () => {} });
  }

  /** Installs an optional browser stack from the UI, then re-reads the settings
   *  so the newly reported availability flips the panel below. */
  async function install(which: "harvester" | "camoufox", fallbackMessage: string) {
    setInstalling(which);
    shell.setFeedback(null);
    try {
      const r = await installBrowser.mutateAsync(which);
      await shell.reload();
      shell.setFeedback({ where: "global", text: r.message || fallbackMessage });
    } catch (e) {
      toasts.fail(e, { retry: () => install(which, fallbackMessage) });
    } finally {
      setInstalling(null);
    }
  }

  return (
    <>
      <SectionHeading icon={Bypass}>{t("settings.scrapingTitle")}</SectionHeading>
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
          <label className="text-xs t-muted block mb-1" htmlFor="scraping-proxy-url">{t("settings.proxyUrl")}</label>
          <input data-action="settings.scraping.proxyUrl" id="scraping-proxy-url" className="input w-full" placeholder={t("settings.proxyUrlPlaceholder")}
            value={values.proxyUrl} onChange={(e) => set("proxyUrl", e.target.value)} />
        </div>
        <div>
          <label className="text-xs t-muted block mb-1" htmlFor="scraping-proxy-pool">{t("settings.proxyPool")}</label>
          <textarea data-action="settings.scraping.proxyPool" id="scraping-proxy-pool" className="input w-full font-mono text-xs" rows={3}
            placeholder={"http://user:pass@proxy1:8000\nhttp://user:pass@proxy2:8000"}
            value={values.proxyUrls} onChange={(e) => set("proxyUrls", e.target.value)} />
          <p className="text-xs t-dim mt-1">{t("settings.proxyPoolNote")}</p>
        </div>
        {/* Idealista's own API: the only option here that is not a workaround,
            so it sits above the ones that are. */}
        <div className="rounded-xl panel p-3 space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium t-body">
            <Credential className="shrink-0" /> {t("settings.idealistaApiTitle")}
          </p>
          <p className="text-xs t-dim">
            {t("settings.idealistaApiNote")}{" "}
            <Link href="https://developers.idealista.com/">developers.idealista.com</Link>
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div>
              <input data-action="settings.scraping.idealistaKey" className="input w-full" type="password"
                placeholder={t(settings.idealista_api_key_set
                  ? "settings.idealistaKeySaved" : "settings.idealistaKeyPlaceholder")}
                value={values.idealistaKey}
                onChange={(e) => set("idealistaKey", e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.idealista_api_key_set}
                  dirty={!!values.idealistaKey.trim()} />
              </div>
            </div>
            <div>
              <input data-action="settings.scraping.idealistaSecret" className="input w-full" type="password"
                placeholder={t(settings.idealista_api_secret_set
                  ? "settings.idealistaSecretSaved" : "settings.idealistaSecretPlaceholder")}
                value={values.idealistaSecret}
                onChange={(e) => set("idealistaSecret", e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.idealista_api_secret_set}
                  dirty={!!values.idealistaSecret.trim()} />
              </div>
            </div>
          </div>
          <label className="text-xs t-muted block">
            {t("settings.idealistaMaxPages")}
            <input data-action="settings.scraping.idealistaMaxPages" className="input w-full sm:w-24 mt-1 block" type="number" min={1}
              value={values.idealistaMaxPages}
              onChange={(e) => set("idealistaMaxPages", Number(e.target.value))} />
          </label>
          <p className="text-xs t-dim">{t("settings.idealistaMaxPagesNote")}</p>
        </div>
        <div className="rounded-xl panel p-3 space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium t-body">
            <Bypass className="shrink-0" /> {t("settings.scrapeApiTitle")}
          </p>
          <p className="text-xs t-dim">{t("settings.scrapeApiNote")}</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <select data-action="settings.scraping.apiProvider" className="input w-full" value={values.apiProvider}
              aria-label={t("settings.scrapeApiTitle")}
              onChange={(e) => set("apiProvider", e.target.value)}>
              <option value="scrapfly">Scrapfly</option>
              <option value="scraperapi">ScraperAPI</option>
              <option value="zyte">Zyte</option>
            </select>
            <div className="sm:col-span-2">
              <input data-action="settings.scraping.apiKey" className="input w-full" type="password"
                placeholder={t(settings.scrape_api_key_set ? "settings.scrapeKeySaved" : "settings.scrapeKeyPlaceholder")}
                value={values.apiKey} onChange={(e) => set("apiKey", e.target.value)} />
              <div className="mt-1">
                <SecretStatus set={settings.scrape_api_key_set} dirty={!!values.apiKey.trim()} />
              </div>
            </div>
          </div>
          <div>
            <label className="text-xs t-muted block mb-1" htmlFor="scraping-api-mode">{t("settings.whenToUse")}</label>
            <select data-action="settings.scraping.apiMode" id="scraping-api-mode" className="input w-full sm:w-auto" value={values.apiMode}
              onChange={(e) => set("apiMode", e.target.value)}>
              <option value="fallback">{t("settings.modeFallback")}</option>
              <option value="always">{t("settings.modeAlways")}</option>
            </select>
            <p className="text-xs t-dim mt-1">{t("settings.modeNote")}</p>
          </div>
        </div>
        <div>
          <label className="text-xs t-muted block mb-1" htmlFor="scraping-cookie">{t("settings.cookieLabel")}</label>
          <input data-action="settings.scraping.cookie" id="scraping-cookie" className="input w-full" type="password"
            placeholder={t(settings.datadome_cookie_set ? "settings.cookieSaved" : "settings.cookiePlaceholder")}
            value={values.cookie} onChange={(e) => set("cookie", e.target.value)} />
          <div className="mt-1">
            <SecretStatus set={settings.datadome_cookie_set}
              since={settings.datadome_cookie_updated_at}
              dirty={!!values.cookie.trim()} />
          </div>
        </div>

        {/* Automatic harvesting: only offered when Playwright is installed,
            otherwise the button would just error. The manual paste above
            always stays as the zero-dependency fallback. */}
        <div className="rounded-xl panel p-3 space-y-2">
          <p className="flex items-center gap-1.5 text-xs font-medium t-body">
            <Harvester className="shrink-0" /> {t("settings.harvestTitle")}
          </p>
          {settings.datadome_harvester_available ? (
            <>
              <p className="text-xs t-dim">{t("settings.harvestNote")}</p>
              <div className="flex items-center gap-2">
                <button data-action="settings.scraping.grabCookie" className="btn-ghost" onClick={grabCookie}
                  disabled={grabbing || shell.anyBusy}>
                  <Restart /> {grabbing ? t("settings.openingBrowser") : t("settings.grabCookie")}
                </button>
                {grabbing && (
                  <button data-action="settings.scraping.stopGrab" className="btn-ghost" onClick={stopGrabbingCookie}
                    disabled={stoppingGrab}>
                    {stoppingGrab ? t("app.stopping") : t("app.stop")}
                  </button>
                )}
              </div>
              <label className="flex items-center gap-2 text-xs t-body cursor-pointer pt-1">
                <input data-action="settings.scraping.autoRefresh" type="checkbox" checked={values.autoRefresh}
                  onChange={(e) => set("autoRefresh", e.target.checked)} />
                {t("settings.autoRefreshCookie")}
              </label>
              <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                <input data-action="settings.scraping.browserFirst" type="checkbox" checked={values.browserFirst} className="mt-0.5"
                  onChange={(e) => set("browserFirst", e.target.checked)} />
                <span>{t("settings.browserFirst")}</span>
              </label>
              <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                <input data-action="settings.scraping.browserHeadful" type="checkbox" checked={values.browserHeadful} className="mt-0.5"
                  onChange={(e) => set("browserHeadful", e.target.checked)} />
                <span>{t("settings.browserHeadful")}</span>
              </label>

              <label className="flex items-start gap-2 text-xs t-body cursor-pointer pt-1">
                <input data-action="settings.scraping.humanize" type="checkbox" checked={values.humanize} className="mt-0.5"
                  onChange={(e) => set("humanize", e.target.checked)} />
                <span>{t("settings.browserHumanize")}</span>
              </label>

              <div className="pt-2 mt-1 border-t border-line space-y-1.5">
                <label className="flex items-center gap-2 text-xs t-body">
                  <span className="whitespace-nowrap">{t("settings.browserEngine")}</span>
                  <select data-action="settings.scraping.engine" className="input py-1 w-full sm:w-auto"
                    value={values.engine}
                    onChange={(e) => set("engine", e.target.value)}>
                    <option value="auto">{t("settings.engineAuto")}</option>
                    <option value="camoufox">{t("settings.engineCamoufox")}</option>
                    <option value="chromium">{t("settings.engineChromium")}</option>
                  </select>
                </label>
                <p className="text-2xs t-muted">
                  {t("settings.camoufoxNote")}{" "}
                  {t(settings.camoufox_available
                    ? "settings.camoufoxInstalled"
                    : "settings.camoufoxMissing")}
                </p>
                {!settings.camoufox_available && (
                  <button data-action="settings.scraping.installCamoufox" className="btn-ghost text-xs w-full sm:w-auto"
                    onClick={() => install("camoufox", t("settings.camoufoxInstalledMsg"))}
                    disabled={installing !== null || shell.anyBusy}>
                    {installing === "camoufox"
                      ? t("settings.installingCamoufox")
                      : t("settings.installCamoufox")}
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="space-y-2.5 pt-1">
              <p className="text-xs t-dim">{t("settings.harvesterMissing")}</p>
              <button data-action="settings.scraping.installHarvester" className="btn-ghost text-xs w-full sm:w-auto"
                onClick={() => install("harvester", t("settings.harvesterInstalledMsg"))}
                disabled={installing !== null || shell.anyBusy}>
                {installing === "harvester"
                  ? t("settings.installingHarvester")
                  : t("settings.installHarvester")}
              </button>
              <p className="text-2xs t-muted pt-1">
                {t("settings.manualInstall")}
                <code className="px-1 py-0.5 rounded bg-wash select-all">
                  backend\.venv\Scripts\pip install playwright &amp;&amp; backend\.venv\Scripts\playwright install chromium
                </code>
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
