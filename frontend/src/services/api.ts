/** REST API client layer communicating with the local FastAPI backend via `/api`.
 *  In local development (`start.bat`), Vite proxies requests from port 5173 to 8000.
 *  In production (`serve.bat`), the FastAPI backend serves static frontend files directly. */
import { formatNumber, translateCurrent } from "../i18n";
import type {
  AssistantResult, AvailabilityCheckProgress, AvailabilityCheckSummary,
  BackupFile, CommuteProgress, CommuteSummary,
  GeocodeProgress, GeocodeSummary, ListingAudit, LogTail, MarketVelocity, PricingTrend,
  ProfileBulkResult,
  ProfileResults, Property, PropertyFilters, PropertyPage, ScanStatus, ScraperHealth,
  SearchBuilderParams,
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
export function propertyParams(filters: PropertyFilters): URLSearchParams {
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
  if (filters.max_sqm) params.set("max_sqm", filters.max_sqm);
  if (filters.floor_band) params.set("floor_band", filters.floor_band);
  if (filters.rooms) params.set("rooms", filters.rooms);
  if (filters.portal) params.set("portal", filters.portal);
  if (filters.agency) params.set("agency", filters.agency);
  if (filters.deal) params.set("deal", filters.deal);
  if (filters.min_sqm_price) params.set("min_sqm_price", filters.min_sqm_price);
  if (filters.max_sqm_price) params.set("max_sqm_price", filters.max_sqm_price);
  if (filters.merged_only) params.set("merged_only", "true");
  // Geographic zone: radius and polygon are mutually exclusive, gated on the
  // mode so a stale center/poly left in state can't leak into the query.
  if (filters.geo_mode === "radius" && filters.center_lat && filters.center_lng && filters.radius_m) {
    params.set("center_lat", filters.center_lat);
    params.set("center_lng", filters.center_lng);
    params.set("radius_m", filters.radius_m);
  } else if (filters.geo_mode === "polygon" && filters.poly) {
    params.set("poly", filters.poly);
  }
  if (filters.only_price_drops) params.set("only_price_drops", "true");
  if (filters.only_favorites) params.set("only_favorites", "true");
  return params;
}

export const api = {
  /** Fetch one page of the filtered, sorted property set.
   *
   *  Answers `{items, total, limit, offset}`: `total` is the size of the whole
   *  filtered set, so the caller can tell whether another page exists without
   *  downloading it. `limit: 0` asks for everything — what the map (a pin per
   *  property) and "select all" need, and deliberately not what the poll uses. */
  getProperties(
    filters: PropertyFilters,
    page?: { limit?: number; offset?: number },
  ): Promise<PropertyPage> {
    const params = propertyParams(filters);
    if (page?.limit !== undefined) params.set("limit", String(page.limit));
    if (page?.offset) params.set("offset", String(page.offset));
    return request(`/properties?${params}`);
  },

  /** Fetch one property by id, whatever the grid is currently filtered to.
   *
   *  What an address opens: a link pasted into a fresh tab has no grid behind it
   *  to read the row from, and the property it names may well be one the
   *  recipient's own filters exclude. */
  getProperty(id: number): Promise<Property> {
    return request(`/properties/${id}`);
  },

  /** Direct URL to download the filtered shortlist as a dossier. Not fetched
   *  as JSON: it returns a file (Content-Disposition attachment), so the caller
   *  navigates to it to trigger the browser download. `pdf` is the exception —
   *  it is served inline as a print-ready report, so the caller opens it in a
   *  tab and the browser's own print dialog writes the PDF. */
  exportUrl(filters: PropertyFilters, fmt: "html" | "markdown" | "csv" | "pdf",
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

  /** The stored reading of this listing's text, or null if none was asked for.
   *  Reads the cache only — never the model — so opening a card is free. */
  getPropertyAudit(id: number): Promise<ListingAudit | null> {
    return request(`/properties/${id}/audit`);
  },
  /** Read this listing's text with the configured model (opt-in, one card at a
   *  time). Answers from the stored row when it is about the same text, so a
   *  second press costs nothing; `force` re-asks anyway. */
  auditProperty(id: number, force = false): Promise<ListingAudit> {
    return request(`/properties/${id}/audit${force ? "?force=true" : ""}`, { method: "POST" });
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

  /** Per-portal scraping health: daily block rates, transports, streaks. */
  getScraperHealth(days = 30): Promise<ScraperHealth> {
    return request(`/scraper-health?${new URLSearchParams({ days: String(days) })}`);
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
  /** The listings behind an area's current median €/sqm (the chart's latest
   *  point). Necessarily today's set: snapshots don't store past membership. */
  getPricingTrendComparables(
    contract: string, city: string, zone = "",
  ): Promise<Property[]> {
    const params = new URLSearchParams({ contract, city });
    if (zone) params.set("zone", zone);
    return request(`/pricing-trends/comparables?${params}`);
  },

  /** Immediately launch an asynchronous scrape across all active search profiles. */
  triggerScan(): Promise<{ status: string }> {
    return request("/scrapers/trigger", { method: "POST" });
  },
  /** Poll the status, progress, and next scheduled run time of the scraper background task. */
  getScanStatus(): Promise<ScanStatus> {
    return request("/scrapers/status");
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
  /** Forget cached geocoding misses so "Find coordinates" retries addresses a
   *  transient Nominatim failure froze as permanently "not found". */
  clearGeocodeCache(): Promise<{ cleared: number }> {
    return request("/maintenance/geocode-clear-cache", { method: "POST" });
  },

  /** Route every property/saved-place pair that is not cached yet, via OSRM
   *  (opt-in, batched, paced, cached). The grid only ever *reads* those cached
   *  legs, so this is what makes commute times appear at all. */
  computeCommutes(): Promise<CommuteSummary> {
    return request("/maintenance/commutes", { method: "POST" });
  },
  /** Poll live progress of an ongoing commute batch. */
  commuteProgress(): Promise<CommuteProgress> {
    return request("/maintenance/commute-progress");
  },
  /** Stops the running commute batch cleanly. */
  cancelCommutes(): Promise<{ ok: boolean }> {
    return request("/maintenance/commute-cancel", { method: "POST" });
  },
  /** Forget every routed leg, so moving a saved place cannot leave the old
   *  (still plausible-looking) travel times behind. */
  clearCommuteCache(): Promise<{ cleared: number }> {
    return request("/maintenance/commute-clear-cache", { method: "POST" });
  },

  /** The copies of the database on disk, newest first, plus the folder that
   *  holds them — a real path on the user's machine, and knowing it is what
   *  makes the copies usable outside this app. */
  listBackups(): Promise<{ folder: string; backups: BackupFile[] }> {
    return request("/maintenance/backups");
  },
  /** Copy the database now, ignoring the once-a-day throttle. */
  createBackup(): Promise<BackupFile> {
    return request("/maintenance/backups", { method: "POST" });
  },
  /** Direct URL of one copy. Answers the file itself (Content-Disposition
   *  attachment), so an unauthenticated browser can simply navigate to it. */
  backupUrl(name: string): string {
    return `${BASE}/maintenance/backups/${encodeURIComponent(name)}`;
  },
  /** Replace the live database with one of the copies. Destructive: the current
   *  state is copied aside first and the answer names that copy, so restoring
   *  the wrong file is recoverable. The backend re-opens the database itself,
   *  but the whole UI is now looking at different data — reload after this. */
  restoreBackup(name: string): Promise<{ restored: string; backup: string | null }> {
    return request(`/maintenance/backups/${encodeURIComponent(name)}/restore`, { method: "POST" });
  },
  /** Bring in a `case.db` carried from another install. The body is the file
   *  itself rather than a multipart form — nothing on either side needs a form
   *  parser for a single file. It is validated and filed among the copies;
   *  putting it over the live database is the separate, explicit restore. */
  importBackup(file: File): Promise<BackupFile> {
    return request("/maintenance/backups/import", {
      method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" },
    });
  },

  /** Irreversibly wipe a scope of stored data (Settings → Data management). */
  resetData(scope: "dashboard" | "pricing-snapshots" | "factory"): Promise<{
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

  /** Probe portals (`AdProbe`) to check if dashboard properties are still online. */
  checkProperties(ids: number[]): Promise<AvailabilityCheckSummary> {
    return request("/properties/check", {
      method: "POST", body: JSON.stringify({ ids }),
    });
  },
  /** Probe portals for a single dashboard property and get updated status right away. */
  checkSingleProperty(id: number): Promise<{ property: Property; summary: AvailabilityCheckSummary }> {
    return request(`/properties/${id}/check`, { method: "POST" });
  },
  /** Poll live progress of an ongoing dashboard properties availability check. */
  propertiesCheckProgress(): Promise<AvailabilityCheckProgress> {
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

/** The export URL fetched as a file, for when the API token is on.
 *
 *  `exportUrl` is meant to be *navigated* to — an anchor click or `window.open`
 *  — and a navigation cannot carry an `Authorization` header. So with a token
 *  set, every export answered 401 and the dossier the user asked for arrived as
 *  a page of JSON. This is the same URL (one querystring builder, so the
 *  dossier still mirrors the screen), fetched through the authenticated path
 *  and handed back as a blob the caller can download or open.
 *
 *  The filename comes from the response's own Content-Disposition, so the file
 *  is named exactly as it is on the unauthenticated path.
 */
export async function fetchExport(
  filters: PropertyFilters,
  fmt: "html" | "markdown" | "csv" | "pdf",
  title: string,
): Promise<{ blob: Blob; filename: string }> {
  const token = authToken.get();
  const resp = await fetch(api.exportUrl(filters, fmt, title), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (resp.status === 401) {
    onAuthRequired?.();
    throw new AuthError();
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Error ${resp.status}`);
  }
  const match = /filename="([^"]+)"/.exec(resp.headers.get("Content-Disposition") ?? "");
  return { blob: await resp.blob(), filename: match?.[1] ?? "dossier" };
}

/** One backup file fetched through the authenticated path, for when the API
 *  token is on — the same reason `fetchExport` exists: a navigation cannot
 *  carry an `Authorization` header, so the download would come back 401 and the
 *  browser would save the error page under a `.db` name. */
export async function fetchBackup(name: string): Promise<Blob> {
  const token = authToken.get();
  const resp = await fetch(api.backupUrl(name), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (resp.status === 401) {
    onAuthRequired?.();
    throw new AuthError();
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Error ${resp.status}`);
  }
  return resp.blob();
}

/** Defence in depth for anchors built from scraped URLs: only http(s) may
 *  become a clickable href — a `javascript:` scheme smuggled into a listing
 *  URL must render inert, mirroring how MapView escapes its tooltip HTML. */
export function safeHref(url: string | null | undefined): string {
  return url && /^https?:\/\//i.test(url) ? url : "#";
}

/** Format numeric values into human-readable Euro strings (`€350,000/month`,
 *  `350.000 €/mese`): both the grouping and the suffix follow the chosen
 *  language, via the locale the i18n provider mirrors outside React. */
export function formatPrice(
  value: number | null | undefined,
  contract: "sale" | "rent" = "sale",
): string {
  if (!value) return translateCurrent("common.notAvailable");
  const formatted = formatNumber(value, {
    style: "currency", currency: "EUR", maximumFractionDigits: 0,
  });
  return contract === "rent"
    ? `${formatted}${translateCurrent("common.perMonthSuffix")}`
    : formatted;
}
