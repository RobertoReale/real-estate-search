/** Minimal, dependency-free i18n for the dashboard (English / Italian).
 *
 *  No i18n library on purpose: the same reason the price charts are inline SVG
 *  and the notifier speaks SMTP by hand — the whole surface we need is a lookup
 *  plus `{placeholder}` interpolation, and a library would add a bundle and a
 *  plugin ecosystem to buy nothing.
 *
 *  The dictionaries are FLAT and typed: `it` is declared as `typeof en`, so a
 *  key added to one language and forgotten in the other fails `tsc -b` instead
 *  of silently rendering an English string inside the Italian UI. `t()` takes
 *  `keyof Dict`, so a typo is a compile error too.
 *
 *  The choice lives in localStorage, per device, exactly like the theme toggle
 *  next to it in the navbar. Strings produced by the backend (scan summaries,
 *  API errors, the availability check's `transport` line) stay in English:
 *  they cross the wire already rendered and the server does not know the
 *  browser's choice.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { en } from "./en";
import { it } from "./it";

export type Lang = "en" | "it";
export type Dict = typeof en;
export type TranslationKey = keyof Dict;

const DICTS: Record<Lang, Dict> = { en, it };
export const STORAGE_KEY = "lang";

export const LANGUAGE_NAMES: Record<Lang, string> = {
  en: "English",
  it: "Italiano",
};

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "it";
}

/** Pick the startup language: an explicit past choice wins, otherwise follow
 *  the browser. Anything unrecognised falls back to Italian, the default for
 *  this Italian real-estate dashboard, so a corrupted localStorage value or an
 *  unrecognised browser locale never leaves the UI in the wrong language. */
export function resolveInitialLang(stored: string | null, browserLangs: readonly string[]): Lang {
  if (isLang(stored)) return stored;
  for (const tag of browserLangs) {
    // "it-CH" and "it" both mean Italian; only the primary subtag matters here
    const primary = tag.toLowerCase().split("-")[0];
    if (isLang(primary)) return primary;
  }
  return "it";
}

/** Substitute `{name}` placeholders. An unknown key returns the key itself
 *  rather than an empty string: a visible `nav.scanNow` in the UI is a bug
 *  report, a blank button is a mystery. */
export function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

export function translate(
  lang: Lang,
  key: TranslationKey,
  params?: Record<string, string | number>,
): string {
  // fall back to English for a key the other dictionary somehow lacks; the
  // types prevent it, but a stale build should degrade rather than blank out
  const template = DICTS[lang][key] ?? en[key] ?? key;
  return interpolate(template, params);
}

export type TFunction = (
  key: TranslationKey,
  params?: Record<string, string | number>,
) => string;

/** BCP-47 tag per language, for `Intl` — "it" alone would leave a browser free
 *  to pick a non-Italian regional format for numbers and dates. */
const LOCALES: Record<Lang, string> = { en: "en-IE", it: "it-IT" };

/** The active locale, mirrored outside React.
 *
 *  `formatPrice` (services/api.ts) and the map's raw-HTML tooltips are plain
 *  functions called from places that have no hook: threading a `lang` argument
 *  through every one of them would touch dozens of call sites to carry a value
 *  that is global by nature. `I18nProvider` assigns this synchronously **during
 *  render** — an effect would run one paint too late and the first frame after
 *  a switch would still format the old way.
 */
let currentLocale = LOCALES.en;

export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
  return value.toLocaleString(currentLocale, options);
}

export function formatDate(value: string | number | Date): string {
  return new Date(value).toLocaleDateString(currentLocale);
}

export function formatDateTime(value: string | number | Date): string {
  return new Date(value).toLocaleString(currentLocale);
}

/** Translate outside a component (module-level helpers, raw-HTML builders). */
export function translateCurrent(
  key: TranslationKey,
  params?: Record<string, string | number>,
): string {
  return translate(currentLocale === LOCALES.it ? "it" : "en", key, params);
}

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TFunction;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() =>
    resolveInitialLang(localStorage.getItem(STORAGE_KEY), navigator.languages ?? [navigator.language]),
  );

  // during render, not in an effect: see `currentLocale`
  currentLocale = LOCALES[lang];

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, lang);
    // keeps the document in sync for screen readers and for the browser's own
    // "translate this page?" heuristics
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((next: Lang) => setLangState(next), []);
  const t = useCallback<TFunction>((key, params) => translate(lang, key, params), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // A component rendered outside the provider (a test mounting it bare, an
    // error boundary above the tree) still needs to render words, so degrade
    // to English rather than throwing.
    return { lang: "en", setLang: () => {}, t: (key, params) => translate("en", key, params) };
  }
  return ctx;
}

/** The everyday hook: `const t = useT()`. */
export function useT(): TFunction {
  return useI18n().t;
}
