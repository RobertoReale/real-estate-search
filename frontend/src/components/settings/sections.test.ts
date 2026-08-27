import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Settings } from "../../types";
import { useAssistantSection } from "./AssistantSection";
import { useEmailSection } from "./EmailSection";
import { useMatchSection } from "./MatchSection";
import { useScanningSection } from "./ScanningSection";
import { useScrapingSection } from "./ScrapingSection";
import { useSystemSection } from "./SystemSection";
import { useTelegramSection } from "./TelegramSection";

/**
 * The settings form is split across seven sections, and the save is the union
 * of what each one contributes. That union is the thing worth pinning: a field
 * dropped from a section's `write` stops being saved with nothing failing —
 * the form still renders it, the request still succeeds, and the value just
 * never persists. Same shape of silent loss as a filter dropped from the
 * `propertyParams` codec, and the same reason for a test.
 */

/** Only what the modal itself asks of a section, so the seven differing value
 *  types can sit in one list. */
interface FormSection {
  reset: (s: Settings) => void;
  payload: () => Partial<Settings>;
}

const SECTION_HOOKS: (() => FormSection)[] = [
  useTelegramSection,
  useEmailSection,
  useScanningSection,
  useMatchSection,
  useAssistantSection,
  useScrapingSection,
  useSystemSection,
];

/** Every key the dialog is responsible for saving. Secrets are absent on
 *  purpose — they are conditional, and covered separately below. */
const SAVED_KEYS = [
  "telegram_chat_id", "telegram_enabled",
  "email_enabled", "smtp_host", "smtp_port", "smtp_user", "email_from", "email_to",
  "scan_interval_minutes", "scanning_paused", "health_alert_after_failures",
  "excluded_keywords",
  "match_score_enabled", "dream_max_price", "dream_min_rooms", "dream_min_sqm",
  "dream_min_floor", "dream_keywords", "dream_zones",
  "nl_parser_backend", "llm_base_url", "llm_model",
  "proxy_url", "proxy_urls", "scrape_api_provider", "scrape_api_mode",
  "idealista_api_max_pages",
  "datadome_auto_refresh", "availability_browser_first",
  "availability_browser_headful", "browser_engine", "browser_humanize",
  "api_auth_token",
].sort();

const STORED: Settings = {
  telegram_bot_token: "", telegram_chat_id: "12345", telegram_enabled: true,
  telegram_token_set: true,
  email_enabled: true, smtp_host: "smtp.gmail.com", smtp_port: 465,
  smtp_user: "me@gmail.com", smtp_password: "", smtp_password_set: true,
  email_from: "me@gmail.com", email_to: "you@gmail.com",
  scan_interval_minutes: 120, scanning_paused: true,
  match_score_enabled: true, dream_max_price: 250000, dream_min_rooms: 3,
  dream_min_sqm: 80, dream_min_floor: 2,
  dream_keywords: ["terrazzo", "ascensore"], dream_zones: ["Navigli"],
  excluded_keywords: ["asta", "nuda proprietà"],
  nl_parser_backend: "llm", llm_base_url: "http://localhost:11434/v1",
  llm_api_key: "", llm_api_key_set: true, llm_model: "llama3.1",
  request_delay_seconds: 3, max_pages_per_search: 5,
  health_alert_after_failures: 5,
  proxy_url: "http://one:8000", proxy_urls: ["http://a:8000", "http://b:8000"],
  scrape_api_provider: "zyte", scrape_api_key: "", scrape_api_key_set: true,
  scrape_api_mode: "always",
  idealista_api_key: "", idealista_api_key_set: true,
  idealista_api_secret: "", idealista_api_secret_set: true,
  idealista_api_max_pages: 3,
  datadome_cookie: "", datadome_cookie_set: true, datadome_auto_refresh: true,
  availability_browser_first: true, availability_browser_headful: true,
  browser_engine: "camoufox", browser_humanize: false,
  api_auth_token: "s3cret",
};

/** Mounts every section hook and seeds it from `s`, as the modal's `hydrate`
 *  does. The live `result` handles are returned rather than their current
 *  value, since each `act` replaces the object a hook exposes. */
function seed(s: Settings) {
  return SECTION_HOOKS.map((useSection) => {
    const { result } = renderHook(() => useSection());
    act(() => result.current.reset(s));
    return result;
  });
}

/** The composed request body, exactly as the modal's `persist` builds it. */
function save(sections: { current: FormSection }[]): Partial<Settings> {
  return sections.reduce<Partial<Settings>>(
    (acc, section) => ({ ...acc, ...section.current.payload() }), {});
}

describe("settings sections", () => {
  it("between them save every non-secret key, and no stray ones", () => {
    expect(Object.keys(save(seed(STORED))).sort()).toEqual(SAVED_KEYS);
  });

  it("round-trip every stored value unchanged when nothing is edited", () => {
    const payload = save(seed(STORED)) as Record<string, unknown>;
    const stored = STORED as unknown as Record<string, unknown>;
    for (const key of SAVED_KEYS) {
      // Keyed rather than bare, so a failure names the field that drifted.
      expect({ [key]: payload[key] }).toEqual({ [key]: stored[key] });
    }
  });

  it("omits every secret while its field is untouched, so a save cannot erase one", () => {
    const payload = save(seed(STORED));
    // The server never returns these, so an empty field means "keep what is
    // stored" — sending "" would wipe a working token on any unrelated save.
    expect(payload).not.toHaveProperty("telegram_bot_token");
    expect(payload).not.toHaveProperty("smtp_password");
    expect(payload).not.toHaveProperty("datadome_cookie");
    expect(payload).not.toHaveProperty("scrape_api_key");
    expect(payload).not.toHaveProperty("llm_api_key");
    // Both halves of the Idealista credential, and both matter: saving one
    // without the other leaves the API configured with a key it cannot use.
    expect(payload).not.toHaveProperty("idealista_api_key");
    expect(payload).not.toHaveProperty("idealista_api_secret");
  });

  it("trims a typed secret — except the two that must keep their spaces", () => {
    const telegram = renderHook(() => useTelegramSection()).result;
    act(() => telegram.current.reset(STORED));
    act(() => telegram.current.set("token", "  bot:AAA  "));
    expect(telegram.current.payload().telegram_bot_token).toBe("bot:AAA");

    const assistant = renderHook(() => useAssistantSection()).result;
    act(() => assistant.current.reset(STORED));
    act(() => assistant.current.set("apiKey", " sk-1 "));
    expect(assistant.current.payload().llm_api_key).toBe("sk-1");

    const scraping = renderHook(() => useScrapingSection()).result;
    act(() => scraping.current.reset(STORED));
    act(() => scraping.current.set("apiKey", " zk-2 "));
    act(() => scraping.current.set("idealistaKey", " ik-3 "));
    act(() => scraping.current.set("idealistaSecret", " is-4 "));
    act(() => scraping.current.set("cookie", " dd=xyz "));
    expect(scraping.current.payload().scrape_api_key).toBe("zk-2");
    expect(scraping.current.payload().idealista_api_key).toBe("ik-3");
    expect(scraping.current.payload().idealista_api_secret).toBe("is-4");
    // Untrimmed on purpose: the cookie is copied out of devtools and a stray
    // space is the user's problem to see, not ours to silently alter.
    expect(scraping.current.payload().datadome_cookie).toBe(" dd=xyz ");

    const email = renderHook(() => useEmailSection()).result;
    act(() => email.current.reset(STORED));
    act(() => email.current.set("password", " abcd efgh "));
    // Also untrimmed: a pasted app password keeps the spaces the provider
    // displays it with, and the backend's save_settings is what strips them.
    expect(email.current.payload().smtp_password).toBe(" abcd efgh ");
  });

  it("re-seeding clears the secret fields but keeps the visible ones", () => {
    const { result } = renderHook(() => useTelegramSection());
    act(() => result.current.reset(STORED));
    act(() => result.current.set("token", "typed-but-unsaved"));
    act(() => result.current.reset(STORED));
    expect(result.current.values.token).toBe("");
    expect(result.current.values.chatId).toBe("12345");
  });
});
