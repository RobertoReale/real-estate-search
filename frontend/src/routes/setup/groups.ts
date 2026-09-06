/** What the setup wizard asks for, grouped by what each answer buys.
 *
 *  `DEFAULT_SETTINGS` is fifty-four entries deep and every capability in it is
 *  off until someone turns it on. Offered as a list of settings that is an
 *  afternoon's reading; offered as "here is what you get, and here is what it
 *  costs to have it" it is five questions, four of which most people skip. So
 *  the grouping here is by outcome — staying unblocked, a second source, being
 *  told, how much it fetches, the optional engines — and deliberately not by the
 *  module that owns the field. Two of the five groups mix settings from three
 *  different subsystems, which is the point: the user is not configuring the
 *  scraper, they are trying not to be blocked.
 *
 *  **Nothing here is required.** Every group can be skipped and the app works
 *  with all five skipped — that is what "off by default" means, and a wizard
 *  that invents a mandatory field the code does not have would be lying about
 *  its own product. `configured` says whether a capability is *on*, never
 *  whether the user is finished.
 *
 *  **Nothing is asked that can be detected.** Whether Playwright imports,
 *  whether Camoufox is installed, whether a DataDome cookie is stored and how
 *  old it is — the backend already reports all of it on `GET /api/settings`, so
 *  a field that depends on one of those carries a `needs` and simply is not
 *  offered on a machine that cannot honour it.
 *
 *  **The bind address is not here, and that is a decision.** Invariant 14 — the
 *  backend listens on loopback, and anything wider requires `api_auth_token` —
 *  is the whole of this app's access control. A setup wizard is exactly where
 *  that would get quietly undone, by someone clicking through five screens and
 *  agreeing to "make it reachable from my phone". If widening the bind ever
 *  becomes part of the wizard it has to ask for the token in the same step and
 *  refuse to continue without one; until then the safe thing is that the wizard
 *  cannot open the port at all.
 *
 *  The rules live here rather than in the component for the usual reason: which
 *  fields a machine is offered, and what a group posts, are answerable without
 *  rendering anything, and `groups.test.ts` answers them.
 */
import type { Settings } from "../../types";
import type { TranslationKey } from "../../i18n";
import { splitList } from "../../components/settings/state";

/** The keys the wizard writes. Every one is a `DEFAULT_SETTINGS` entry, and the
 *  template-literal key helpers below turn this union into a set of translation
 *  keys the compiler checks against the dictionary — a field with no label is a
 *  build error rather than a screen showing `setup.field.osrm_url`. */
export type SetupKey =
  | "datadome_cookie" | "datadome_auto_refresh" | "browser_engine"
  | "proxy_urls" | "scrape_api_key" | "scrape_api_mode"
  | "idealista_api_key" | "idealista_api_secret"
  | "telegram_bot_token" | "telegram_chat_id" | "telegram_enabled"
  | "smtp_host" | "smtp_port" | "smtp_user" | "smtp_password"
  | "email_from" | "email_to" | "email_enabled"
  | "max_pages_per_search" | "request_delay_seconds" | "idealista_api_max_pages"
  | "nominatim_url" | "osrm_url" | "llm_base_url" | "llm_api_key" | "llm_model";

export type GroupId = "unblocked" | "source" | "told" | "pace" | "engines";

/** How a field is drawn, and how its text becomes a value again. `secret` is a
 *  `text` that is never seeded and never posted empty; see `payloadFor`. */
export type FieldKind = "text" | "secret" | "number" | "list" | "toggle" | "select";

/** Everything the wizard's selects can offer, as a closed set for the same
 *  reason `SetupKey` is one: the label key is derived from the value. */
export type SetupOptionValue = "auto" | "chromium" | "camoufox" | "fallback" | "always";

/** The values a select offers. `needs` drops one the machine cannot honour —
 *  Camoufox is a choice only where Camoufox is installed. */
export interface SetupOption {
  readonly value: SetupOptionValue;
  readonly needs?: (s: Settings) => boolean;
}

export interface SetupField {
  readonly key: SetupKey;
  readonly kind: FieldKind;
  /** Offered only when this holds of the machine. Absent means always. */
  readonly needs?: (s: Settings) => boolean;
  /** `select` only. */
  readonly options?: readonly SetupOption[];
  /** `secret` only: the `*_set` boolean that says one is already stored, so the
   *  field can report "saved" without ever holding the value. */
  readonly stored?: (s: Settings) => boolean;
  /** `number` only: whether a fraction is meaningful. The backend types these
   *  as `int` apart from the delay, and 4.5 pages is a validation error. */
  readonly fractional?: true;
}

export interface SetupGroup {
  readonly id: GroupId;
  readonly fields: readonly SetupField[];
  /** Whether this capability is switched on. Absent where the group only tunes
   *  something that already works: a fetch pace has a working default, so it is
   *  never "missing" and never appears in what is left to do. */
  readonly configured?: (s: Settings) => boolean;
}

/** A form's worth of strings and ticks. Numbers and lists live here as the text
 *  the user typed, because a half-typed number is not a number and a field that
 *  rewrites itself under the cursor is worse than one that accepts nonsense
 *  until it is posted. */
export type SetupValues = Record<string, string | boolean>;

/** In the order they are asked. Being unblocked comes first because it is the
 *  one that decides whether anything works at all; the optional engines come
 *  last because the app is complete without them. */
export const GROUPS: readonly SetupGroup[] = [
  {
    id: "unblocked",
    configured: (s) => s.datadome_cookie_set || s.scrape_api_key_set || s.proxy_urls.length > 0,
    fields: [
      { key: "datadome_cookie", kind: "secret", stored: (s) => s.datadome_cookie_set },
      {
        key: "datadome_auto_refresh", kind: "toggle",
        // The refresh drives a real browser. Offering the switch where
        // Playwright is not importable is offering a setting that cannot do
        // anything, and the backend already says which it is.
        needs: (s) => s.datadome_harvester_available,
      },
      {
        key: "browser_engine", kind: "select",
        needs: (s) => s.datadome_harvester_available || s.camoufox_available,
        options: [
          { value: "auto" },
          { value: "chromium" },
          { value: "camoufox", needs: (s) => s.camoufox_available },
        ],
      },
      { key: "proxy_urls", kind: "list" },
      { key: "scrape_api_key", kind: "secret", stored: (s) => s.scrape_api_key_set },
      {
        key: "scrape_api_mode", kind: "select",
        options: [{ value: "fallback" }, { value: "always" }],
      },
    ],
  },
  {
    id: "source",
    configured: (s) => s.idealista_api_key_set && s.idealista_api_secret_set,
    fields: [
      { key: "idealista_api_key", kind: "secret", stored: (s) => s.idealista_api_key_set },
      { key: "idealista_api_secret", kind: "secret", stored: (s) => s.idealista_api_secret_set },
    ],
  },
  {
    id: "told",
    configured: (s) =>
      (s.telegram_enabled && s.telegram_token_set && s.telegram_chat_id !== "")
      || (s.email_enabled && s.smtp_host !== "" && s.email_to !== ""),
    fields: [
      { key: "telegram_bot_token", kind: "secret", stored: (s) => s.telegram_token_set },
      { key: "telegram_chat_id", kind: "text" },
      { key: "telegram_enabled", kind: "toggle" },
      { key: "smtp_host", kind: "text" },
      { key: "smtp_port", kind: "number" },
      { key: "smtp_user", kind: "text" },
      { key: "smtp_password", kind: "secret", stored: (s) => s.smtp_password_set },
      { key: "email_from", kind: "text" },
      { key: "email_to", kind: "text" },
      { key: "email_enabled", kind: "toggle" },
    ],
  },
  {
    id: "pace",
    fields: [
      { key: "max_pages_per_search", kind: "number" },
      { key: "request_delay_seconds", kind: "number", fractional: true },
      { key: "idealista_api_max_pages", kind: "number" },
    ],
  },
  {
    id: "engines",
    configured: (s) => s.nominatim_url !== "" || s.osrm_url !== "" || s.llm_api_key_set,
    fields: [
      { key: "nominatim_url", kind: "text" },
      { key: "osrm_url", kind: "text" },
      { key: "llm_base_url", kind: "text" },
      { key: "llm_api_key", kind: "secret", stored: (s) => s.llm_api_key_set },
      { key: "llm_model", kind: "text" },
    ],
  },
];

export const GROUP_IDS = GROUPS.map((g) => g.id);

export function groupAt(index: number): SetupGroup {
  return GROUPS[Math.min(Math.max(index, 0), GROUPS.length - 1)];
}

/** The fields this machine is actually offered. */
export function fieldsFor(group: SetupGroup, s: Settings): readonly SetupField[] {
  return group.fields.filter((f) => !f.needs || f.needs(s));
}

/** The options this machine is actually offered. */
export function optionsFor(field: SetupField, s: Settings): readonly SetupOptionValue[] {
  return (field.options ?? []).filter((o) => !o.needs || o.needs(s)).map((o) => o.value);
}

/** Seeds one group's form from the saved settings.
 *
 *  A secret always seeds empty, never to the `"***"` the API answers with. That
 *  is the whole of the round trip on this side: an empty secret box means "keep
 *  the stored one", so the wizard cannot post the mask back as a value however
 *  many groups the user walks through afterwards. */
export function seed(group: SetupGroup, s: Settings): SetupValues {
  const values: SetupValues = {};
  for (const field of fieldsFor(group, s)) {
    const stored = s[field.key];
    switch (field.kind) {
      case "secret": values[field.key] = ""; break;
      case "toggle": values[field.key] = stored === true; break;
      case "list": values[field.key] = Array.isArray(stored) ? stored.join(", ") : ""; break;
      case "number": values[field.key] = String(stored ?? ""); break;
      default: values[field.key] = typeof stored === "string" ? stored : "";
    }
  }
  return values;
}

/** What this group posts. Only its own fields, and only the ones that carry an
 *  answer: an untouched secret and an emptied number are both left out, so the
 *  save is a patch over the stored settings rather than a replacement of them.
 *  `SettingsIn` drops the nulls on the way in, which is what makes a partial
 *  payload safe — see `backend/app/routers/settings.py`. */
export function payloadFor(
  group: SetupGroup, values: SetupValues, s: Settings,
): Partial<Settings> {
  const payload: Record<string, unknown> = {};
  for (const field of fieldsFor(group, s)) {
    const raw = values[field.key];
    switch (field.kind) {
      case "toggle":
        payload[field.key] = raw === true;
        break;
      case "secret": {
        // Nothing typed: the stored secret stays. Posting `""` would erase it
        // and posting `"***"` would replace a working key with three asterisks,
        // and neither is what an untouched field means.
        const typed = String(raw ?? "").trim();
        if (typed) payload[field.key] = typed;
        break;
      }
      case "list":
        payload[field.key] = splitList(String(raw ?? ""));
        break;
      case "number": {
        const parsed = Number(String(raw ?? "").trim());
        if (String(raw ?? "").trim() === "" || !Number.isFinite(parsed)) break;
        payload[field.key] = field.fractional ? parsed : Math.round(parsed);
        break;
      }
      default:
        payload[field.key] = String(raw ?? "").trim();
    }
  }
  return payload as Partial<Settings>;
}

/** The capabilities still switched off, in the order they are asked for. What
 *  the Settings dialog lists so the wizard is not a one-shot: a user who skipped
 *  Telegram in March can see in April that they never set it up. */
export function pendingGroups(s: Settings): GroupId[] {
  return GROUPS.filter((g) => g.configured && !g.configured(s)).map((g) => g.id);
}

/** The dictionary keys, derived. The template literal is a union of exactly the
 *  keys these tables can produce, so a missing translation fails `tsc` rather
 *  than rendering its own key at the user. */
export function groupTitleKey(id: GroupId): TranslationKey {
  return `setup.group.${id}`;
}

export function groupBodyKey(id: GroupId): TranslationKey {
  return `setup.body.${id}`;
}

export function fieldLabelKey(key: SetupKey): TranslationKey {
  return `setup.field.${key}`;
}

export function fieldHintKey(key: SetupKey): TranslationKey {
  return `setup.hint.${key}`;
}

export function optionLabelKey(value: SetupOptionValue): TranslationKey {
  return `setup.option.${value}`;
}
