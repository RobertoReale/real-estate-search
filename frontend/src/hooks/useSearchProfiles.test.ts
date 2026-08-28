/** The one answer shape the assistant panel did not survive: no searches.
 *
 * `POST /api/search-assistant` answers `{"searches": []}` whenever the query
 * splits into nothing but separators — `parse_query` drops every blank segment
 * (verified against the backend with ";" and "; ;"). The panel read
 * `searches[0]` unconditionally, so `undefined` reached `paramsFromAssistant`
 * and the thrown TypeError was caught and printed as the assistant's answer.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useSearchProfiles } from "./useSearchProfiles";
import { en } from "../i18n/en";
import { api } from "../services/api";

function setUp() {
  return renderHook(() =>
    useSearchProfiles({ profiles: [], settings: null, onChanged: vi.fn() }),
  );
}

describe("the assistant with an answer it cannot use", () => {
  it("asks for a real query instead of reporting a JavaScript error", async () => {
    vi.spyOn(api, "askAssistant").mockResolvedValue({ searches: [] });
    const { result } = setUp();

    act(() => result.current.setQuery(";"));
    await act(async () => { await result.current.ask(); });

    expect(result.current.error).toBe(en["profiles.assistantNothing"]);
    // and it stays where it was rather than opening a builder over nothing
    expect(result.current.mode).toBe("closed");
    expect(result.current.assistant).toBeNull();
  });

  it("still opens the builder on the ordinary single-search answer", async () => {
    vi.spyOn(api, "askAssistant").mockResolvedValue({
      searches: [{
        params: {
          city: "Milano", province: "", zone: "", contract: "sale",
          min_price: null, max_price: 400000, min_rooms: 3, max_rooms: null,
          min_sqm: null,
        },
        interpretation: [], notes: [], warnings: [], urls: null,
      }],
    });
    const { result } = setUp();

    act(() => result.current.setQuery("trilocale a Milano"));
    await act(async () => { await result.current.ask(); });

    await waitFor(() => expect(result.current.mode).toBe("builder"));
    expect(result.current.params.city).toBe("Milano");
    expect(result.current.error).toBe("");
  });
});
