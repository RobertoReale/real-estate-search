/**
 * The frame every screen is drawn in: what this is, where you can go, and what
 * the scanner is doing.
 *
 * It is the outermost layout route, so it mounts once and stays mounted for the
 * whole session. That is load-bearing rather than incidental: the event stream
 * is opened here, and a shell rendered per screen would tear the connection
 * down and reopen it on every navigation.
 *
 * **The navigation is one element in two shapes, not two elements.** Below `lg`
 * it is a bar pinned to the bottom of the screen, where a thumb reaches; from
 * `lg` up it is a row in the header, where the room is. Rendering it twice and
 * hiding one copy would put two of every destination in the tab order and two
 * of every `data-action` in the page, and the inventory would be counting
 * renderings instead of controls.
 *
 * **The scan is a status, not a paragraph.** One icon and one line: where the
 * scanning is up to, and what the last run found. It is truncated rather than
 * shortened — the whole of it is in the page, and the title carries the long
 * form for a pointer. A three-line block of prose beside the buttons is what
 * this replaced, and it was the widest thing in the header for something nobody
 * reads twice.
 *
 * It lives in `src/ui/` because it is the frame and not a screen: it knows
 * nothing about a property, a filter or a portal. The one fact it does report —
 * that a scan is running — it reads through the same query as everything else.
 * It is deliberately absent from the barrel: `index.ts` is the set a screen is
 * drawn *with*, and the shell is what draws the screens.
 */
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { LANGUAGE_NAMES, useI18n, type TranslationKey } from "../i18n";
import { useDataVersionSync, useScanStatus, useTriggerScan } from "../queries/dashboard";
import { useEventStream } from "../queries/events";
import { INSIGHTS, LISTINGS, LOGS, SEARCHES, SETTINGS, withSearch } from "../routes/params";
import { useToasts } from "../components/Toast";
import { Button } from "./Button";
import {
  Brand, Cog, Insights, Language, Listings, Logs, Paused, Run, Scheduled,
  Searches, ThemeDark, ThemeLight, type Icon,
} from "./icons";
import { cx } from "./tone";

/** The four places, in the order they are offered. Listings is first because it
 *  is the default, and Settings is last because it is the one a user visits
 *  once. Each carries its own inventory id, which is also its label key — one
 *  name for the destination, wherever it is referred to. */
const DESTINATIONS: { path: string; id: TranslationKey; Glyph: Icon }[] = [
  { path: LISTINGS, id: "nav.listings", Glyph: Listings },
  { path: INSIGHTS, id: "nav.insights", Glyph: Insights },
  { path: SEARCHES, id: "nav.searches", Glyph: Searches },
  { path: SETTINGS, id: "nav.settings", Glyph: Cog },
];

export default function AppShell() {
  const { lang, setLang, t } = useI18n();
  const toasts = useToasts();
  const { search } = useLocation();
  // light is the default; dark only if the user chose it before
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  const scanStatus = useScanStatus().data ?? null;
  const triggerScan = useTriggerScan();
  // One connection for the session, opened at the outermost layout route so
  // moving between the four places does not reopen it.
  useEventStream();
  // Every screen is re-read when the backend's fingerprint of the property set
  // moves, and only then.
  useDataVersionSync(scanStatus ?? undefined);

  const running = scanStatus?.running ?? false;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  // Two languages, so the picker is a toggle like the theme button rather than
  // a dropdown: one tap, and it survives a 390 px header.
  const otherLang = lang === "it" ? "en" : "it";
  const switchLangLabel = t("nav.languageSwitchTo", { language: LANGUAGE_NAMES[otherLang] });

  const nextRun = scanStatus?.next_auto_run
    ? new Date(scanStatus.next_auto_run).toLocaleTimeString(lang, {
        hour: "2-digit", minute: "2-digit",
      })
    : null;

  // What the status says, and what the pointer gets on hover. The short form is
  // what fits on one line beside the navigation; the long form is what the old
  // three-line paragraph said, and it is the tooltip. Nothing is dropped — the
  // line is truncated by CSS rather than shortened, so the whole of it is still
  // in the page for anyone reading it with something other than their eyes.
  const state: { glyph: ReactNode; short: string; long: string; tone?: string } | null =
    running ? {
      glyph: <Run />, short: t("nav.scanning"), long: t("nav.scanning"),
      tone: "accent-link animate-pulse",
    }
    : scanStatus?.paused ? {
      glyph: <Paused />, short: t("nav.pausedShort"), long: t("nav.paused"),
      tone: "text-caution-ink",
    }
    : nextRun ? {
      glyph: <Scheduled />, short: t("nav.nextScanShort", { time: nextRun }),
      long: t("nav.nextScan", { time: nextRun }),
    }
    : null;
  // The last scan's summary is the other half of "where the scanning is up to",
  // and it is the half a user actually wants: what the last run found. It is
  // read out after the state so the two make one sentence.
  const line = [state?.short, scanStatus?.last_summary].filter(Boolean).join(" · ");
  const detail = [state?.long, scanStatus?.last_summary].filter(Boolean).join(" — ");

  function scanNow() {
    triggerScan.mutate(undefined, {
      onError: (e) => toasts.fail(e, { doing: t("toast.scanFailed"), retry: scanNow }),
    });
  }

  return (
    // The bottom bar is fixed, so it would sit on top of the last row of
    // whatever screen is open. The padding is the space it occupies, given back.
    <div className="min-h-screen pb-16 lg:pb-0">
      <header className="glass sticky top-0 z-40 px-3 sm:px-6 py-3 flex items-center gap-2 sm:gap-4">
        {/* min-w-0 lets the title truncate instead of pushing the buttons off a
            phone screen: the controls are what must survive the narrow layout */}
        <div className="flex items-center gap-2 mr-auto lg:mr-0 min-w-0">
          <Brand size={24} className="shrink-0 text-accent-ink" />
          <div className="min-w-0">
            <h1 className="font-bold text-base sm:text-lg leading-tight truncate">
              {t("nav.title")}
            </h1>
            <p className="text-xs t-muted leading-tight hidden sm:block">
              {t("nav.subtitle")}
            </p>
          </div>
        </div>

        {/* One node, two shapes — see the note at the top of this file. The
            phone shape repeats what `.glass` does rather than reusing it: the
            class has no `max-lg` form, and a bar that is transparent on a
            laptop is a bar with a border across the middle of the header. */}
        <nav aria-label={t("nav.primary")}
          className="flex items-stretch justify-around gap-1
            max-lg:fixed max-lg:inset-x-0 max-lg:bottom-0 max-lg:z-40 max-lg:px-2 max-lg:py-1
            max-lg:bg-surface/90 max-lg:backdrop-blur-xl max-lg:border-t max-lg:border-line
            lg:justify-start lg:mr-auto">
          {DESTINATIONS.map(({ path, id, Glyph }) => (
            <NavLink key={path} to={withSearch(path, search)} data-action={id}
              className={({ isActive }) => cx(
                "flex flex-col lg:flex-row items-center justify-center gap-0.5 lg:gap-1.5",
                "flex-1 lg:flex-none rounded-control px-2 lg:px-3 py-1.5 text-xs lg:text-sm",
                "font-medium transition btn-focus",
                isActive ? "text-accent-ink bg-accent-soft" : "t-muted hover:text-ink",
              )}>
              <Glyph size={18} />
              {t(id)}
            </NavLink>
          ))}
        </nav>

        {/* One line, and never more than one: `max-w` plus `truncate` is what
            keeps a long summary from pushing the buttons off the row, and what
            makes this a status element rather than the paragraph it replaced. */}
        {line && (
          <p role="status" title={detail}
            className={cx("hidden lg:flex items-center gap-1.5 shrink-0 text-xs t-muted",
              state?.tone)}>
            {state?.glyph}
            <span className="truncate max-w-[24ch]">{line}</span>
          </p>
        )}

        {/* Every control here is `shrink-0`, so the padding is what decides
            whether the row fits: at 390px with the longer Italian labels four
            of them ran 3px past the viewport and scrolled the whole document
            sideways. Tight on a phone, roomier from `sm` up.

            The `!` is load-bearing. `Button` already sets `px-4` for its default
            size, and Tailwind resolves two utilities from the same group by
            stylesheet order rather than by the order they appear in the class
            attribute — so a plain `px-2` here would lose, and the row would go
            back to being four px-4 buttons.

            Icon-only, but deliberately `Button` with an `aria-label` rather than
            `IconButton`: the latter is square by construction, and a 40px square
            is 6px wider than what these are today. Three of them is the 18px
            that used to push this row past a 390px viewport. */}
        <Button data-action="scan.now" variant="solid" tone="accent"
          className="shrink-0 !px-3 sm:!px-4" onClick={scanNow}
          disabled={running} aria-label={t("nav.scanNowAria")}>
          {running ? (
            t("nav.running")
          ) : (
            <>
              <Run />
              <span className="sm:hidden">{t("nav.scanNowShort")}</span>
              <span className="hidden sm:inline">{t("nav.scanNow")}</span>
            </>
          )}
        </Button>
        <Button data-action="nav.language" className="shrink-0 !px-2 sm:!px-3 font-semibold !text-xs"
          onClick={() => setLang(otherLang)}
          title={switchLangLabel} aria-label={switchLangLabel}>
          <Language size={16} />
          {lang.toUpperCase()}
        </Button>
        <Button data-action="nav.theme" className="shrink-0 !px-2 sm:!px-4" onClick={() => setDark(!dark)}
          title={dark ? t("nav.toLight") : t("nav.toDark")}
          aria-label={dark ? t("nav.toLight") : t("nav.toDark")}>
          {dark ? <ThemeLight size={18} /> : <ThemeDark size={18} />}
        </Button>
        {/* `asChild`, with the id on the anchor rather than on the wrapper: the
            element that navigates is the one the user operates, and it is the
            one the inventory has to name. */}
        <Button className="shrink-0 !px-2 sm:!px-4" asChild>
          <NavLink data-action="nav.logs" to={withSearch(LOGS, search)}
            title={t("nav.viewLog")} aria-label={t("nav.viewLog")}>
            <Logs size={18} />
          </NavLink>
        </Button>
      </header>

      <main className="max-w-7xl mx-auto p-3 sm:p-6 space-y-4 sm:space-y-6">
        <Outlet />
      </main>
    </div>
  );
}
