import { describe, expect, it } from "vitest";

import {
  GROUPS, fieldsFor, fieldHintKey, fieldLabelKey, groupAt, groupBodyKey, groupTitleKey,
  optionLabelKey, optionsFor, payloadFor, pendingGroups, seed,
  type SetupGroup,
} from "./groups";
import { en } from "../../i18n/en";
import { settingsFixture } from "../../test/settings";

function group(id: string): SetupGroup {
  const found = GROUPS.find((g) => g.id === id);
  if (!found) throw new Error(`no group ${id}`);
  return found;
}

describe("what a machine is offered", () => {
  it("hides the automatic cookie refresh where the harvester is not installed", () => {
    const s = settingsFixture({ datadome_harvester_available: false });
    const keys = fieldsFor(group("unblocked"), s).map((f) => f.key);
    expect(keys).not.toContain("datadome_auto_refresh");
    expect(keys).not.toContain("browser_engine");
    // What the user could still act on is untouched: the point is not to hide a
    // step, it is not to offer a switch that cannot do anything.
    expect(keys).toContain("datadome_cookie");
    expect(keys).toContain("proxy_urls");
  });

  it("offers it where it is", () => {
    const s = settingsFixture({ datadome_harvester_available: true });
    expect(fieldsFor(group("unblocked"), s).map((f) => f.key))
      .toContain("datadome_auto_refresh");
  });

  it("offers Camoufox as an engine only where Camoufox is installed", () => {
    const engine = group("unblocked").fields.find((f) => f.key === "browser_engine");
    if (!engine) throw new Error("no browser_engine field");

    const playwrightOnly = settingsFixture({ datadome_harvester_available: true });
    const both = settingsFixture({
      datadome_harvester_available: true, camoufox_available: true,
    });
    expect(optionsFor(engine, playwrightOnly)).toEqual(["auto", "chromium"]);
    expect(optionsFor(engine, both)).toEqual(["auto", "chromium", "camoufox"]);
  });
});

describe("seeding a step", () => {
  it("never seeds a secret, so the mask cannot be typed back as a value", () => {
    // This is the round trip's near half. `GET /api/settings` answers "***" for
    // a stored secret; seeding a box with it and posting the form back would
    // overwrite a working key with three asterisks.
    const s = settingsFixture({
      datadome_cookie: "***", datadome_cookie_set: true,
      scrape_api_key: "***", scrape_api_key_set: true,
    });
    const values = seed(group("unblocked"), s);
    expect(values.datadome_cookie).toBe("");
    expect(values.scrape_api_key).toBe("");
  });

  it("seeds the rest from what is stored", () => {
    const s = settingsFixture({
      proxy_urls: ["http://a:8000", "http://b:8000"],
      scrape_api_mode: "always",
      max_pages_per_search: 12,
    });
    expect(seed(group("unblocked"), s).proxy_urls).toBe("http://a:8000, http://b:8000");
    expect(seed(group("unblocked"), s).scrape_api_mode).toBe("always");
    expect(seed(group("pace"), s).max_pages_per_search).toBe("12");
  });

  it("seeds a toggle as a boolean rather than as its text", () => {
    const s = settingsFixture({ telegram_enabled: true });
    expect(seed(group("told"), s).telegram_enabled).toBe(true);
  });
});

describe("what a step posts", () => {
  const s = settingsFixture();

  it("posts nothing at all for a step nobody touched, except the toggles", () => {
    // A toggle always carries an answer — unticked is a value — but an empty
    // text box is "leave it alone", not "make it empty".
    const payload = payloadFor(group("source"), seed(group("source"), s), s);
    expect(payload).toEqual({});
  });

  it("leaves an untouched secret out and sends a typed one", () => {
    const values = { ...seed(group("source"), s), idealista_api_key: "  abc123  " };
    expect(payloadFor(group("source"), values, s))
      .toEqual({ idealista_api_key: "abc123" });
  });

  it("only ever posts its own group's fields", () => {
    const values = { ...seed(group("pace"), s), telegram_chat_id: "12345" };
    expect(Object.keys(payloadFor(group("pace"), values, s)))
      .not.toContain("telegram_chat_id");
  });

  it("skips a number the user emptied rather than posting a zero", () => {
    const values = { ...seed(group("pace"), s), max_pages_per_search: "" };
    expect(payloadFor(group("pace"), values, s)).not.toHaveProperty("max_pages_per_search");
  });

  it("rounds the counts and keeps the delay's fraction", () => {
    const values = {
      ...seed(group("pace"), s),
      max_pages_per_search: "4.7", request_delay_seconds: "2.5",
    };
    const payload = payloadFor(group("pace"), values, s) as Record<string, unknown>;
    expect(payload.max_pages_per_search).toBe(5);
    expect(payload.request_delay_seconds).toBe(2.5);
  });

  it("splits a list the way the settings dialog does, trailing comma and all", () => {
    const values = {
      ...seed(group("unblocked"), s), proxy_urls: " http://a:1 , http://b:2 , ",
    };
    const payload = payloadFor(group("unblocked"), values, s) as Record<string, unknown>;
    expect(payload.proxy_urls).toEqual(["http://a:1", "http://b:2"]);
  });
});

describe("what is still switched off", () => {
  it("counts every capability on a fresh install, and never the fetch pace", () => {
    // The pace has working defaults, so it is not something the user is missing.
    expect(pendingGroups(settingsFixture()))
      .toEqual(["unblocked", "source", "told", "engines"]);
  });

  it("drops a group as soon as any one way of having it is configured", () => {
    expect(pendingGroups(settingsFixture({ scrape_api_key_set: true })))
      .not.toContain("unblocked");
    expect(pendingGroups(settingsFixture({ proxy_urls: ["http://a:1"] })))
      .not.toContain("unblocked");
    expect(pendingGroups(settingsFixture({
      telegram_enabled: true, telegram_token_set: true, telegram_chat_id: "1",
    }))).not.toContain("told");
  });

  it("does not count a secret that is saved but switched off", () => {
    // A token stored with the channel disabled sends nothing, and telling the
    // user it is set up would be a lie they only discover by not being alerted.
    expect(pendingGroups(settingsFixture({
      telegram_token_set: true, telegram_chat_id: "1", telegram_enabled: false,
    }))).toContain("told");
  });

  it("needs both halves of the Idealista credentials", () => {
    expect(pendingGroups(settingsFixture({ idealista_api_key_set: true })))
      .toContain("source");
  });
});

describe("the step sequence", () => {
  it("asks about staying unblocked first and the extras last", () => {
    expect(GROUPS.map((g) => g.id))
      .toEqual(["unblocked", "source", "told", "pace", "engines"]);
  });

  it("clamps rather than falling off either end", () => {
    expect(groupAt(-3).id).toBe("unblocked");
    expect(groupAt(99).id).toBe("engines");
  });
});

describe("the words", () => {
  it("has a title, a body, a label, a hint and an option label for everything", () => {
    // `tsc` proves the derived keys are in the dictionary's key union, which
    // catches a field added without a label. It cannot catch the other half:
    // a key present but written as an empty string. So this asserts the text.
    for (const g of GROUPS) {
      expect(en[groupTitleKey(g.id)], `title for ${g.id}`).toBeTruthy();
      expect(en[groupBodyKey(g.id)], `body for ${g.id}`).toBeTruthy();
      for (const field of g.fields) {
        expect(en[fieldLabelKey(field.key)], `label for ${field.key}`).toBeTruthy();
        expect(en[fieldHintKey(field.key)], `hint for ${field.key}`).toBeTruthy();
        for (const option of field.options ?? []) {
          expect(en[optionLabelKey(option.value)], `label for ${option.value}`).toBeTruthy();
        }
      }
    }
  });
});
