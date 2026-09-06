/** A settings object as a fresh install answers with: every capability off,
 *  every secret unset, nothing detected.
 *
 *  `SettingsOut` is sixty-odd required fields, so a test that wants to say "a
 *  machine where Camoufox is installed" would otherwise spell out the other
 *  sixty to say it. The overrides argument is the whole point: the fixture is
 *  the baseline, and each test names only the difference it is about.
 */
import type { Settings } from "../types";

const EMPTY: Settings = {
  telegram_bot_token: "", telegram_chat_id: "", telegram_enabled: false,
  telegram_actions_enabled: false, telegram_token_set: false,
  email_enabled: false, smtp_host: "", smtp_port: 587, smtp_user: "",
  smtp_password: "", smtp_password_set: false, email_from: "", email_to: "",
  scan_interval_minutes: 60, scanning_paused: false,
  match_score_enabled: false, dream_max_price: 0, dream_min_rooms: 0,
  dream_min_sqm: 0, dream_min_floor: 0, dream_keywords: [], dream_zones: [],
  excluded_keywords: [],
  nominatim_url: "", geocode_after_scan: false,
  commute_enabled: false, osrm_url: "", commute_points: [],
  nl_parser_backend: "heuristic", llm_base_url: "", llm_api_key: "",
  llm_api_key_set: false, llm_model: "", listing_audit_enabled: false,
  request_delay_seconds: 3, max_pages_per_search: 5,
  split_large_searches: false, scan_portals_concurrently: false,
  stop_when_nothing_new: false, full_sweep_every_days: 7,
  health_alert_after_failures: 3,
  proxy_url: "", proxy_urls: [],
  scrape_api_provider: "", scrape_api_key: "", scrape_api_key_set: false,
  scrape_api_mode: "fallback", transport_escalate_after_failures: 2,
  idealista_api_key: "", idealista_api_key_set: false,
  idealista_api_secret: "", idealista_api_secret_set: false,
  idealista_api_max_pages: 1,
  tls_impersonations: [],
  datadome_cookie: "", datadome_cookie_set: false, datadome_auto_refresh: false,
  datadome_cookie_updated_at: "", datadome_cookie_ttl_minutes: 45,
  datadome_harvester_available: false,
  availability_browser_first: false, availability_browser_headful: false,
  browser_engine: "auto", camoufox_available: false, browser_humanize: false,
  repair_agency_prefixes: [],
  omi_input_dir: "",
  setup_completed: false,
  api_auth_token: "",
};

export function settingsFixture(overrides: Partial<Settings> = {}): Settings {
  return { ...EMPTY, ...overrides };
}
