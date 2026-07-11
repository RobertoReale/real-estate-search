import type {
  AssistantResult, EmailScanParams, EmailScanProgress, EmailScanSummary,
  ImportCheckProgress, ImportCheckSummary, ImportedListing,
  ImportFilters, MarketVelocity, Property, PropertyFilters, ScanStatus,
  SearchBuilderParams, SearchBuilderUrls, SearchProfile, Settings,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Error ${resp.status}`);
  }
  return resp.json();
}

export const api = {
  getProperties(filters: PropertyFilters): Promise<Property[]> {
    const params = new URLSearchParams();
    params.set("status", filters.status);
    params.set("contract", filters.contract);
    params.set("sort", filters.sort);
    if (filters.city) params.set("city", filters.city);
    if (filters.min_price) params.set("min_price", filters.min_price);
    if (filters.max_price) params.set("max_price", filters.max_price);
    if (filters.min_sqm) params.set("min_sqm", filters.min_sqm);
    if (filters.rooms) params.set("rooms", filters.rooms);
    if (filters.only_price_drops) params.set("only_price_drops", "true");
    if (filters.only_favorites) params.set("only_favorites", "true");
    return request(`/properties?${params}`);
  },
  deleteProperty(id: number) {
    return request(`/properties/${id}`, { method: "DELETE" });
  },
  restoreProperty(id: number) {
    return request<{ ok: boolean }>(`/properties/${id}/restore`, { method: "POST" });
  },
  updateProperty(id: number, data: { is_favorite?: boolean; notes?: string }) {
    return request<Property>(`/properties/${id}`, {
      method: "PATCH", body: JSON.stringify(data),
    });
  },

  getProfiles(): Promise<SearchProfile[]> {
    return request("/search-profiles");
  },
  createProfile(data: Partial<SearchProfile>) {
    return request<SearchProfile>("/search-profiles", {
      method: "POST", body: JSON.stringify(data),
    });
  },
  updateProfile(id: number, data: Partial<SearchProfile>) {
    return request<SearchProfile>(`/search-profiles/${id}`, {
      method: "PUT", body: JSON.stringify(data),
    });
  },
  deleteProfile(id: number) {
    return request(`/search-profiles/${id}`, { method: "DELETE" });
  },

  buildSearchUrls(params: SearchBuilderParams): Promise<SearchBuilderUrls> {
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
    };
    return request("/search-builder", {
      method: "POST", body: JSON.stringify(body),
    });
  },

  askAssistant(query: string): Promise<AssistantResult> {
    return request("/search-assistant", {
      method: "POST", body: JSON.stringify({ query }),
    });
  },

  getMarketVelocity(contract: string, city?: string): Promise<MarketVelocity> {
    const params = new URLSearchParams({ contract });
    if (city) params.set("city", city);
    return request(`/market-velocity?${params}`);
  },

  triggerScan(): Promise<{ status: string }> {
    return request("/scrapers/trigger", { method: "POST" });
  },
  getScanStatus(): Promise<ScanStatus> {
    return request("/scrapers/status");
  },

  getSettings(): Promise<Settings> {
    return request("/settings");
  },
  updateSettings(data: Partial<Settings>) {
    return request<Settings>("/settings", {
      method: "PUT", body: JSON.stringify(data),
    });
  },
  telegramTest() {
    return request("/settings/telegram-test", { method: "POST" });
  },
  datadomeRefresh(portal: "immobiliare" | "idealista" = "immobiliare") {
    return request<{ ok: boolean; portal: string; updated_at: string; cookie_preview: string }>(
      `/settings/datadome-refresh?portal=${portal}`, { method: "POST" },
    );
  },
  emailTest() {
    return request("/settings/email-test", { method: "POST" });
  },

  imapTest(): Promise<{ ok: boolean; detail: string }> {
    return request("/email-import/test", { method: "POST" });
  },
  emailImportScan(params: EmailScanParams): Promise<EmailScanSummary> {
    return request("/email-import/scan", {
      method: "POST", body: JSON.stringify(params),
    });
  },
  emailImportProgress(): Promise<EmailScanProgress> {
    return request("/email-import/progress");
  },
  getImportedListings(filters: Partial<ImportFilters>): Promise<ImportedListing[]> {
    const params = new URLSearchParams();
    if (filters.profile_id) params.set("profile_id", filters.profile_id);
    if (filters.contract) params.set("contract", filters.contract);
    if (filters.city) params.set("city", filters.city);
    if (filters.min_price) params.set("min_price", filters.min_price);
    if (filters.max_price) params.set("max_price", filters.max_price);
    if (filters.rooms) params.set("rooms", filters.rooms);
    if (filters.q) params.set("q", filters.q);
    return request(`/email-import?${params}`);
  },
  acceptImported(id: number): Promise<{ ok: boolean; property_id: number }> {
    return request(`/email-import/${id}/accept`, { method: "POST" });
  },
  discardImported(id: number) {
    return request(`/email-import/${id}/discard`, { method: "POST" });
  },
  bulkImported(ids: number[], action: "accept" | "discard") {
    return request<{ ok: boolean; processed: number }>("/email-import/bulk", {
      method: "POST", body: JSON.stringify({ ids, action }),
    });
  },
  checkImported(ids: number[]): Promise<ImportCheckSummary> {
    return request("/email-import/check", {
      method: "POST", body: JSON.stringify({ ids }),
    });
  },
  importCheckProgress(): Promise<ImportCheckProgress> {
    return request("/email-import/check-progress");
  },
};

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
