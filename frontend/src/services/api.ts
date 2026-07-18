/** REST API client layer communicating with the local FastAPI backend via `/api`.
 *  In local development (`start.bat`), Vite proxies requests from port 5173 to 8000.
 *  In production (`serve.bat`), the FastAPI backend serves static frontend files directly. */
import type {
  AssistantResult, EmailScanParams, EmailScanProgress,
  EmailScanSummary, GeocodeProgress, GeocodeSummary, ImportCheckProgress, ImportCheckSummary, ImportedListing,
  ImportFilters, LogTail, MarketVelocity, PricingTrend, ProfileBulkResult,
  ProfileResults, Property, PropertyFilters, ScanStatus, SearchBuilderParams,
  SearchBuilderUrls, SearchProfile, SearchProfileParams, Settings, Tag, TrendArea,
} from "../types";

const BASE = "/api";

/** Optional shared-secret API token (invariant 14 relaxed). Kept in
 *  localStorage so it survives reloads; attached to every request as a Bearer
 *  header. Empty string when the backend has auth off — the common case. */
const TOKEN_KEY = "apiToken";
export const authToken = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

/** Thrown on a 401 so the app can show the token prompt instead of a red toast. */
export class AuthError extends Error {
  constructor() {
    super("Authentication required");
    this.name = "AuthError";
  }
}

/** Set by the app so any 401 anywhere can surface the login gate. */
let onAuthRequired: (() => void) | null = null;
export function setAuthRequiredHandler(fn: () => void) {
  onAuthRequired = fn;
}

/** Execute an HTTP request against the backend REST endpoint, throwing formatted JSON errors on failure. */
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = authToken.get();
  const resp = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (resp.status === 401) {
    onAuthRequired?.();
    throw new AuthError();
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Error ${resp.status}`);
  }
  return resp.json();
}

/** The current filters as query params — shared by the grid fetch and the
 *  export download so a dossier holds exactly the filtered set on screen. */
function propertyParams(filters: PropertyFilters): URLSearchParams {
  const params = new URLSearchParams();
  params.set("status", filters.status);
  params.set("contract", filters.contract);
  params.set("sort", filters.sort);
  if (filters.city) params.set("city", filters.city);
  if (filters.zone) params.set("zone", filters.zone);
  if (filters.q) params.set("q", filters.q);
  if (filters.source) params.set("source", filters.source);
  if (filters.profile_id) params.set("profile_id", filters.profile_id);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.min_price) params.set("min_price", filters.min_price);
  if (filters.max_price) params.set("max_price", filters.max_price);
  if (filters.min_sqm) params.set("min_sqm", filters.min_sqm);
  if (filters.rooms) params.set("rooms", filters.rooms);
  if (filters.only_price_drops) params.set("only_price_drops", "true");
  if (filters.only_favorites) params.set("only_favorites", "true");
  return params;
}

export const api = {
  /** Fetch a filtered and sorted list of properties (`active`, `filtered`, `gone`, `hidden`, or `all`). */
  getProperties(filters: PropertyFilters): Promise<Property[]> {
    return request(`/properties?${propertyParams(filters)}`);
  },

  /** Direct URL to download the filtered shortlist as a dossier. Not fetched
   *  as JSON: it returns a file (Content-Disposition attachment), so the caller
   *  navigates to it to trigger the browser download. */
  exportUrl(filters: PropertyFilters, fmt: "html" | "markdown" | "csv",
            title: string): string {
    const params = propertyParams(filters);
    params.set("fmt", fmt);
    if (title) params.set("title", title);
    return `${BASE}/properties/export?${params}`;
  },
  /** Hide a property from active views (moves status to `hidden`). */
  deleteProperty(id: number) {
    return request(`/properties/${id}`, { method: "DELETE" });
  },
  /** Restore a previously hidden/sold property back to `active` status. */
  restoreProperty(id: number) {
    return request<{ ok: boolean }>(`/properties/${id}/restore`, { method: "POST" });
  },
  /** Mark a property as sold/rented out (status `sold`, a confirmed close). */
  markPropertySold(id: number) {
    return request<{ ok: boolean }>(`/properties/${id}/sold`, { method: "POST" });
  },
  /** Apply hide/restore/favorite/unfavorite/sold/add_tag/remove_tag to many
   *  selected properties at once (`tag_id` required for the last two). */
  bulkProperties(
    ids: number[],
    action: "hide" | "restore" | "favorite" | "unfavorite" | "sold" | "add_tag" | "remove_tag",
    tagId?: number,
  ) {
    return request<{ ok: boolean; processed: number }>("/properties/bulk", {
      method: "POST", body: JSON.stringify({ ids, action, tag_id: tagId ?? null }),
    });
  },
  /** Patch user-curated property metadata (`is_favorite` flag, custom `notes`,
   *  or the full tag set via `tag_ids` — a full replace, not additive). */
  updateProperty(id: number, data: { is_favorite?: boolean; notes?: string; tag_ids?: number[] }) {
    return request<Property>(`/properties/${id}`, {
      method: "PATCH", body: JSON.stringify(data),
    });
  },

  /** Resolve a single property's map coordinates on demand — the card's "View
   *  on map" button when the pin is missing. Returns the updated property and
   *  whether it now has coordinates (fail-open: `located: false` is not an
   *  error, just an address too vague to place). */
  geocodeProperty(id: number): Promise<{ property: Property; located: boolean }> {
    return request(`/properties/${id}/geocode`, { method: "POST" });
  },

  /** All user-defined tags with usage counts (dashboard filter + tag picker autocomplete). */
  getTags(): Promise<Tag[]> {
    return request("/tags");
  },
  /** Create a tag, or reuse an existing one on a case-insensitive name match. */
  createTag(name: string): Promise<Tag> {
    return request("/tags", { method: "POST", body: JSON.stringify({ name }) });
  },
  /** Delete a tag globally, detaching it from every property that carried it. */
  deleteTag(id: number) {
    return request<{ ok: boolean }>(`/tags/${id}`, { method: "DELETE" });
  },

  /** Retrieve all configured search profiles along with diagnostic failure counts. */
  getProfiles(): Promise<SearchProfile[]> {
    return request("/search-profiles");
  },
  /** Create a new portal search profile. */
  createProfile(data: Partial<SearchProfile>) {
    return request<SearchProfile>("/search-profiles", {
      method: "POST", body: JSON.stringify(data),
    });
  },
  /** Update configuration or notification toggles for an existing search profile. */
  updateProfile(id: number, data: Partial<SearchProfile>) {
    return request<SearchProfile>(`/search-profiles/${id}`, {
      method: "PUT", body: JSON.stringify(data),
    });
  },
  /** How many dashboard properties the selected searches produced, and how many
   *  deleting them would remove — shown in the delete dialog before the user
   *  chooses. Asked for the whole selection at once: a property found by two of
   *  the searches being deleted is not "kept by another search". */
  getProfilesResults(ids: number[]): Promise<ProfileResults> {
    return request("/search-profiles/results", {
      method: "POST", body: JSON.stringify({ ids }),
    });
  },
  /** Apply activate/pause/notify/delete to the selected searches (one included).
   *  With `delete_results` the properties they alone produced go with them. */
  bulkProfiles(
    ids: number[],
    action: "activate" | "pause" | "notify" | "delete",
    opts: { notifyChannels?: string; deleteResults?: boolean } = {},
  ): Promise<ProfileBulkResult> {
    return request("/search-profiles/bulk", {
      method: "POST",
      body: JSON.stringify({
        ids, action,
        notify_channels: opts.notifyChannels ?? "",
        delete_results: opts.deleteResults ?? false,
      }),
    });
  },

  /** Generate native search URLs from structured criteria (`city`, `rooms`, `price`).
   *
   *  `verify` asks the backend to check, with one live request, whether
   *  Idealista knows this zone's slug: only then can it use the precise zone
   *  page instead of the broader free-text search. It is off for calls that
   *  merely re-derive a URL to prefill a form. */
  buildSearchUrls(params: SearchBuilderParams, verify = false): Promise<SearchBuilderUrls> {
    // empty strings become nulls the backend understands as "no filter"
    const body = {
      city: params.city,
      province: params.province,
      zone: params.zone,
      contract: params.contract,
      min_price: params.min_price ? Number(params.min_price) : null,
      max_price: params.max_price ? Number(params.max_price) : null,
      min_rooms: params.min_rooms ? Number(params.min_rooms) : null,
      max_rooms: params.max_rooms ? Number(params.max_rooms) : null,
      min_sqm: params.min_sqm ? Number(params.min_sqm) : null,
      verify,
    };
    return request("/search-builder", {
      method: "POST", body: JSON.stringify(body),
    });
  },

  /** Extract structured criteria offline from an existing portal search URL. */
  parseSearchUrl(url: string): Promise<SearchProfileParams> {
    return request("/search-builder/parse", {
      method: "POST", body: JSON.stringify({ url }),
    });
  },

  /** Parse a natural-language search query offline into structured parameters. */
  askAssistant(query: string): Promise<AssistantResult> {
    return request("/search-assistant", {
      method: "POST", body: JSON.stringify({ query }),
    });
  },

  /** Compute area days-on-market velocities and agency pricing behavior. */
  getMarketVelocity(contract: string, city?: string): Promise<MarketVelocity> {
    const params = new URLSearchParams({ contract });
    if (city) params.set("city", city);
    return request(`/market-velocity?${params}`);
  },

  /** Areas that have enough daily snapshots to plot a price trend. */
  getTrendAreas(contract: string): Promise<TrendArea[]> {
    return request(`/pricing-trends/areas?${new URLSearchParams({ contract })}`);
  },
  /** Median €/sqm over time for one area (empty zone = whole city). */
  getPricingTrends(contract: string, city: string, zone = ""): Promise<PricingTrend> {
    const params = new URLSearchParams({ contract, city });
    if (zone) params.set("zone", zone);
    return request(`/pricing-trends?${params}`);
  },

  /** Immediately launch an asynchronous scrape across all active search profiles. */
  triggerScan(): Promise<{ status: string }> {
    return request("/scrapers/trigger", { method: "POST" });
  },
  /** Poll the status, progress, and next scheduled run time of the scraper background task. */
  getScanStatus(): Promise<ScanStatus> {
    return request("/scrapers/status");
  },
  /** Instantly repair existing dashboard properties lacking city, zone, title, or photos, and merge duplicate cards sharing the same listing URL. */
  repairListings(): Promise<{
    properties_fixed: number;
    listings_fixed: number;
    images_recovered: number;
    properties_merged: number;
    duplicate_listings_removed: number;
  }> {
    return request("/maintenance/repair-listings", { method: "POST" });
  },
  /** Backfill map coordinates for properties with an address/zone but no pin,
   *  via Nominatim (opt-in, batched, paced, cached). */
  geocodeMissing(): Promise<GeocodeSummary> {
    return request("/maintenance/geocode-missing", { method: "POST" });
  },
  /** Poll live progress of an ongoing geocoding operation. */
  geocodeProgress(): Promise<GeocodeProgress> {
    return request("/maintenance/geocode-progress");
  },
  /** Stops the running geocoding operation cleanly. */
  cancelGeocode(): Promise<{ ok: boolean }> {
    return request("/maintenance/geocode-cancel", { method: "POST" });
  },

  /** Irreversibly wipe a scope of stored data (Settings → Data management). */
  resetData(scope: "email-import" | "dashboard" | "pricing-snapshots" | "factory"): Promise<{
    scope: string; deleted: Record<string, number>; backup?: string | null;
  }> {
    return request(`/maintenance/reset/${scope}`, { method: "POST" });
  },

  /** Restart the backend process so a code update takes effect. The connection
   *  drops briefly; the caller polls a lightweight endpoint until it answers. */
  restartBackend(): Promise<{ ok: boolean; reload: boolean }> {
    return request("/system/restart", { method: "POST" });
  },

  /** Load current user preferences and API credentials. */
  getSettings(): Promise<Settings> {
    return request("/settings");
  },
  /** Persist modified application settings to `settings.json`. */
  updateSettings(data: Partial<Settings>) {
    return request<Settings>("/settings", {
      method: "PUT", body: JSON.stringify(data),
    });
  },
  /** Send a test broadcast message to verify Telegram bot credentials. */
  telegramTest() {
    return request("/settings/telegram-test", { method: "POST" });
  },
  /** Trigger an automated DataDome cookie refresh via local browser if Playwright is installed. */
  datadomeRefresh(portal: "immobiliare" | "idealista" = "immobiliare") {
    return request<{ ok: boolean; portal: string; updated_at: string; cookie_preview: string }>(
      `/settings/datadome-refresh?portal=${portal}`, { method: "POST" },
    );
  },
  /** Stops a running cookie grab at its next poll (a no-op if nothing is running). */
  cancelDatadomeRefresh() {
    return request<{ ok: boolean }>("/settings/datadome-refresh/cancel", { method: "POST" });
  },
  /** Install Playwright and Chromium into the active backend environment. */
  installHarvester() {
    return request<{ ok: boolean; message: string }>("/settings/install-harvester", { method: "POST" });
  },
  /** Install Camoufox (stealth Firefox) + its browser binary into the backend. */
  installCamoufox() {
    return request<{ ok: boolean; message: string }>("/settings/install-camoufox", { method: "POST" });
  },
  /** Send a test notification message to verify SMTP email settings. */
  emailTest() {
    return request("/settings/email-test", { method: "POST" });
  },

  /** Verify IMAP connection and authentication against the mail server. */
  imapTest(): Promise<{ ok: boolean; detail: string }> {
    return request("/email-import/test", { method: "POST" });
  },
  /** Launch a read-only IMAP search across the inbox for portal alert emails. */
  emailImportScan(params: EmailScanParams): Promise<EmailScanSummary> {
    return request("/email-import/scan", {
      method: "POST", body: JSON.stringify(params),
    });
  },
  /** Poll current progress metrics of an active IMAP inbox scan. */
  emailImportProgress(): Promise<EmailScanProgress> {
    return request("/email-import/progress");
  },
  /** Query listings extracted from alert emails staged for user review. */
  getImportedListings(filters: Partial<ImportFilters>): Promise<ImportedListing[]> {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status);
    if (filters.profile_id) params.set("profile_id", filters.profile_id);
    if (filters.contract) params.set("contract", filters.contract);
    if (filters.city) params.set("city", filters.city);
    if (filters.min_price) params.set("min_price", filters.min_price);
    if (filters.max_price) params.set("max_price", filters.max_price);
    if (filters.rooms) params.set("rooms", filters.rooms);
    if (filters.q) params.set("q", filters.q);
    return request(`/email-import?${params}`);
  },
  /** Accept a staged listing into the active database (`upsert_listing`). */
  acceptImported(id: number): Promise<{ ok: boolean; property_id: number }> {
    return request(`/email-import/${id}/accept`, { method: "POST" });
  },
  /** Discard an unwanted staged listing (retained to prevent re-importing on future scans). */
  discardImported(id: number) {
    return request(`/email-import/${id}/discard`, { method: "POST" });
  },
  /** Bulk accept or discard multiple staged listings. */
  bulkImported(ids: number[], action: "accept" | "discard") {
    return request<{ ok: boolean; processed: number }>("/email-import/bulk", {
      method: "POST", body: JSON.stringify({ ids, action }),
    });
  },
  /** Probe portals (`AdProbe`) to check if staged listings are still online. */
  checkImported(ids: number[]): Promise<ImportCheckSummary> {
    return request("/email-import/check", {
      method: "POST", body: JSON.stringify({ ids }),
    });
  },
  /** Poll live progress of an ongoing portal availability check (`AdProbe`). */
  importCheckProgress(): Promise<ImportCheckProgress> {
    return request("/email-import/check-progress");
  },
  /** Probe portals (`AdProbe`) to check if dashboard properties are still online. */
  checkProperties(ids: number[]): Promise<ImportCheckSummary> {
    return request("/properties/check", {
      method: "POST", body: JSON.stringify({ ids }),
    });
  },
  /** Probe portals for a single dashboard property and get updated status right away. */
  checkSingleProperty(id: number): Promise<{ property: Property; summary: ImportCheckSummary }> {
    return request(`/properties/${id}/check`, { method: "POST" });
  },
  /** Poll live progress of an ongoing dashboard properties availability check. */
  propertiesCheckProgress(): Promise<ImportCheckProgress> {
    return request("/properties/check-progress");
  },
  /** Stops the running dashboard properties availability check after its
   * current property (a no-op if nothing is running). */
  cancelPropertiesCheck(): Promise<{ ok: boolean }> {
    return request("/properties/check/cancel", { method: "POST" });
  },
  /** Last N lines of the backend's own app.log, for the in-app log viewer. */
  logsTail(lines = 200): Promise<LogTail> {
    return request(`/logs/tail?lines=${lines}`);
  },
};

/** Defence in depth for anchors built from scraped URLs: only http(s) may
 *  become a clickable href — a `javascript:` scheme smuggled into a listing
 *  URL must render inert, mirroring how MapView escapes its tooltip HTML. */
export function safeHref(url: string | null | undefined): string {
  return url && /^https?:\/\//i.test(url) ? url : "#";
}

/** Format numeric values into human-readable Euro strings (`€350,000` or `€1,200/month`). */
export function formatPrice(
  value: number | null | undefined,
  contract: "sale" | "rent" = "sale",
): string {
  if (!value) return "N/A";
  const formatted = value.toLocaleString("en-IE", {
    style: "currency", currency: "EUR", maximumFractionDigits: 0,
  });
  return contract === "rent" ? `${formatted}/month` : formatted;
}
