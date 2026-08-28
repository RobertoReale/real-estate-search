/** Grouping the monitored searches, and the one string in here the user reads.
 *
 * `getBaseName` is not a component, so it had a hard-coded English fallback
 * where the rest of the UI calls `t()`. That name is a heading in the searches
 * panel and an option in the grid's "Limit to search" dropdown, so it showed an
 * English phrase inside an otherwise Italian screen — the exact failure the
 * "never hardcode a user-facing string" rule exists to prevent.
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { getBaseName, groupSearchProfiles } from "./searchProfiles";
import { I18nProvider, STORAGE_KEY } from "../i18n";
import { en } from "../i18n/en";
import { it as itDict } from "../i18n/it";
import type { SearchProfile } from "../types";

/** Puts the module-level locale (the one `translateCurrent` reads) into the
 *  given language, the way the running app does — by rendering the provider. */
function activateLanguage(lang: "en" | "it") {
  localStorage.setItem(STORAGE_KEY, lang);
  render(<I18nProvider><span /></I18nProvider>);
}

const profile = (over: Partial<SearchProfile>): SearchProfile => ({
  id: 1, name: "", portal: "immobiliare", search_url: "https://example.test",
  excluded_keywords: "", notify_channels: "", is_active: true,
  last_run_at: null, last_run_status: "ok", last_run_detail: "",
  consecutive_failures: 0, ...over,
});

describe("getBaseName", () => {
  it("takes the unnamed fallback from the active dictionary, not a literal", () => {
    // an English literal here reads the same in an English UI, so the Italian
    // one is the test that can tell the two apart
    activateLanguage("it");
    expect(getBaseName("")).toBe(itDict["profiles.untitled"]);
    expect(getBaseName("   ")).toBe(itDict["profiles.untitled"]);

    activateLanguage("en");
    expect(getBaseName("")).toBe(en["profiles.untitled"]);
  });

  it("strips the portal suffix a paired search carries", () => {
    expect(getBaseName("Navigli - Trilocale (immobiliare)")).toBe("Navigli - Trilocale");
    expect(getBaseName("Navigli - Trilocale - IDEALISTA")).toBe("Navigli - Trilocale");
  });
});

describe("groupSearchProfiles", () => {
  it("folds the same search on both portals into one row", () => {
    const groups = groupSearchProfiles([
      profile({ id: 1, name: "Navigli (immobiliare)", portal: "immobiliare" }),
      profile({ id: 2, name: "Navigli (idealista)", portal: "idealista" }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].baseName).toBe("Navigli");
    expect(groups[0].portals).toEqual(["immobiliare", "idealista"]);
  });

  it("is active only when every portal in the group is", () => {
    const groups = groupSearchProfiles([
      profile({ id: 1, name: "Navigli (immobiliare)", is_active: true }),
      profile({ id: 2, name: "Navigli (idealista)", portal: "idealista", is_active: false }),
    ]);
    expect(groups[0].is_active).toBe(false);
  });
});
