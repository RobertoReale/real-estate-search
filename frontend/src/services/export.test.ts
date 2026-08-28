/** The dossier export against the optional API token.
 *
 * `exportUrl` is built to be *navigated* to — `window.open` for the print-ready
 * PDF, a transient anchor for HTML/MD/CSV — and a navigation cannot carry an
 * `Authorization` header. So with `api_auth_token` set, all four export buttons
 * hit the middleware's 401 and the dossier arrived as a page of JSON: the
 * dashboard's own 401 handling never saw it either, because nothing went
 * through `request()`. Remote access is the reason to set a token at all, and
 * handing someone a dossier is the reason to export — so the two features
 * cancelled each other out.
 *
 * `fetchExport` is the authenticated path. It must reuse the very same URL, or
 * the dossier stops mirroring the screen.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthError, api, authToken, fetchExport, propertyParams } from "./api";
import type { PropertyFilters } from "../types";

const FILTERS: PropertyFilters = {
  status: "active", contract: "sale", city: "Milano", zone: "", q: "",
  source: "", profile_id: "", tag: "", min_price: "", max_price: "250000",
  min_sqm: "", max_sqm: "", floor_band: "", rooms: "",
  portal: "", agency: "", deal: "", min_sqm_price: "", max_sqm_price: "",
  merged_only: false,
  geo_mode: "", center_lat: "", center_lng: "", radius_m: "", poly: "",
  only_price_drops: false, only_favorites: true, sort: "newest",
};

function response(init: Partial<Response> & { body?: string } = {}): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "Content-Disposition": 'attachment; filename="dossier-20260828.csv"' }),
    blob: async () => new Blob([init.body ?? "id,price"]),
    json: async () => ({}),
    ...init,
  } as unknown as Response;
}

afterEach(() => {
  authToken.clear();
  vi.restoreAllMocks();
});

describe("fetchExport", () => {
  it("sends the token a navigation cannot carry", async () => {
    authToken.set("s3cret");
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    await fetchExport(FILTERS, "csv", "Favourites in Milano");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer s3cret");
  });

  it("asks for exactly the URL the navigation would have used", async () => {
    // one querystring builder for the grid and the dossier is what makes an
    // export mirror the screen; a second one here would drift from it
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    await fetchExport(FILTERS, "csv", "Favourites in Milano");

    expect(fetchMock.mock.calls[0][0])
      .toBe(api.exportUrl(FILTERS, "csv", "Favourites in Milano"));
    // and that URL still carries the filters on screen
    const params = propertyParams(FILTERS);
    expect(params.get("city")).toBe("Milano");
    expect(params.get("only_favorites")).toBe("true");
  });

  it("takes the filename from the response, as the browser would have", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response()));
    const { filename } = await fetchExport(FILTERS, "csv", "t");
    expect(filename).toBe("dossier-20260828.csv");
  });

  it("raises the token prompt on a 401 rather than saving the error page", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: false, status: 401 })));
    await expect(fetchExport(FILTERS, "pdf", "t")).rejects.toBeInstanceOf(AuthError);
  });

  it("surfaces any other failure with the backend's own message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      response({ ok: false, status: 500, json: async () => ({ detail: "boom" }) }),
    ));
    await expect(fetchExport(FILTERS, "html", "t")).rejects.toThrow("boom");
  });
});
