"""Pydantic schemas for REST API input/output."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ListingOut(BaseModel):
    """API response model representing a single portal ad linked to a Property."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    portal: str
    portal_id: str
    url: str
    price: float | None
    agency: str
    description: str
    image_url: str
    first_seen_at: datetime
    last_seen_at: datetime


class PriceHistoryOut(BaseModel):
    """API response model recording a historical price variation of a Property."""
    model_config = ConfigDict(from_attributes=True)

    old_price: float | None
    new_price: float
    changed_at: datetime


class PropertyOut(BaseModel):
    """Comprehensive API response model for a deduplicated physical property,
    including its associated listings, price changes, and transient market statistics."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    city: str
    zone: str
    address: str
    latitude: float | None
    longitude: float | None
    rooms: int | None
    floor: str
    sqm: float | None
    contract: str = "sale"
    current_min_price: float | None
    first_price: float | None
    image_url: str
    status: str
    filtered_reason: str
    is_favorite: bool = False
    notes: str = ""
    # market position vs local median €/sqm (computed per request,
    # see services/pricing_stats.py; None when not enough comparables)
    area_median_sqm_price: float | None = None
    area_median_scope: str | None = None  # "zone" | "city"
    sqm_price_delta_pct: float | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    listings: list[ListingOut] = []
    price_history: list[PriceHistoryOut] = []


class PropertyPatch(BaseModel):
    """User-curated fields; scans never touch them."""
    is_favorite: bool | None = None
    notes: str | None = None


class SearchProfileIn(BaseModel):
    """Input payload for creating or modifying a monitored portal search profile."""
    name: str
    search_url: str
    excluded_keywords: str = ""
    notify_channels: str = ""  # CSV among telegram,email; empty = all enabled
    is_active: bool = True

    @field_validator("search_url")
    @classmethod
    def validate_portal_url(cls, v: str) -> str:
        v = v.strip()
        if "immobiliare.it" not in v and "idealista.it" not in v:
            raise ValueError(
                "The URL must come from immobiliare.it or idealista.it"
            )
        return v


class SearchProfileOut(BaseModel):
    """API response model detailing a search profile along with its execution diagnostics."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    portal: str
    search_url: str
    excluded_keywords: str
    notify_channels: str
    is_active: bool
    last_run_at: datetime | None
    last_run_status: str
    last_run_detail: str
    consecutive_failures: int = 0


class SettingsIn(BaseModel):
    """Input payload representing user-configurable application preferences."""
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_enabled: bool | None = None
    email_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    email_import_auto_scan: bool | None = None
    email_import_auto_scan_interval_hours: int | None = None
    scan_interval_minutes: int | None = None
    excluded_keywords: list[str] | None = None
    request_delay_seconds: float | None = None
    max_pages_per_search: int | None = None
    health_alert_after_failures: int | None = None
    proxy_url: str | None = None
    datadome_cookie: str | None = None
    datadome_auto_refresh: bool | None = None
    datadome_cookie_ttl_minutes: int | None = None

    @field_validator("health_alert_after_failures")
    @classmethod
    def failures_not_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("must be >= 0 (0 disables health alerting)")
        return v

    @field_validator("email_import_auto_scan_interval_hours")
    @classmethod
    def import_interval_at_least_hourly(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("must be >= 1 hour")
        return v


class SearchBuilderIn(BaseModel):
    """Structured parameters the search builder turns into portal URLs."""
    city: str
    province: str = ""
    zone: str = ""  # neighborhood; slugs are best-effort (verified by the user)
    contract: str = "sale"  # sale | rent
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: int | None = None

    @field_validator("city")
    @classmethod
    def city_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("City is required")
        return v.strip()

    @field_validator("contract")
    @classmethod
    def contract_valid(cls, v: str) -> str:
        if v not in ("sale", "rent"):
            raise ValueError("contract must be 'sale' or 'rent'")
        return v


class AssistantQueryIn(BaseModel):
    """Free-text query for the natural-language search assistant."""
    query: str


class AssistantParams(BaseModel):
    """What the parser understood: same shape as SearchBuilderIn, except
    `city` may be empty (the parser could not identify one)."""
    city: str = ""
    province: str = ""
    zone: str = ""
    contract: str = "sale"
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: int | None = None


class AssistantSearch(BaseModel):
    """One search alternative the assistant understood. A query with
    disjunctions ("bilocale in zona X o trilocale in zona Y") yields one of
    these per alternative."""
    params: AssistantParams
    # human-readable read-back of the query, shown before anything is saved
    interpretation: list[str] = []
    notes: list[str] = []       # assumptions the parser had to make
    warnings: list[str] = []    # what it could not resolve
    # None when no city was found: a city-less portal URL would silently
    # search all of Italy (see invariant #7)
    urls: dict[str, str] | None = None


class AssistantOut(BaseModel):
    searches: list[AssistantSearch]


class EmailImportScanIn(BaseModel):
    """How to look for listing emails in the user's inbox (IMAP read-only)."""
    # portals = messages sent by the portals' own alert addresses
    # address = messages from user-specified senders (agencies, etc.)
    # any     = any message mentioning the portals anywhere (slowest net)
    mode: str = "portals"
    senders: str = ""        # CSV, used by mode="address"
    since_days: int = 365
    max_emails: int = 200

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, v: str) -> str:
        if v not in ("portals", "address", "any"):
            raise ValueError("mode must be 'portals', 'address' or 'any'")
        return v

    @field_validator("since_days", "max_emails")
    @classmethod
    def positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be >= 1")
        return v


class ImportedListingOut(BaseModel):
    """API response model representing a listing extracted from an alert email."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    portal: str
    portal_id: str
    url: str
    title: str
    price: float | None
    city: str
    zone: str
    rooms: int | None
    sqm: float | None
    contract: str
    email_from: str
    email_subject: str
    email_date: datetime | None
    status: str  # pending | accepted | discarded
    property_id: int | None
    # None = never checked against the portal, which is not the same as "gone"
    is_available: bool | None
    last_checked_at: datetime | None
    created_at: datetime


class ImportBulkIn(BaseModel):
    """Payload for bulk acceptance or rejection of email-staged listings."""
    ids: list[int]
    action: str  # accept | discard

    @field_validator("action")
    @classmethod
    def action_valid(cls, v: str) -> str:
        if v not in ("accept", "discard"):
            raise ValueError("action must be 'accept' or 'discard'")
        return v


class ImportCheckIn(BaseModel):
    """Which staged listings to verify against the portal — one HTTP request
    each, spaced by `request_delay_seconds`. Capped server-side: this is an
    on-demand probe, not a crawl."""
    ids: list[int]


class AreaVelocityOut(BaseModel):
    """Aggregated market speed metrics for a specific neighborhood or city."""
    city: str
    zone: str
    scope: str            # "zone" | "city"
    sample: int
    closed: int           # how many left the market ("gone")
    median_days_to_gone: float | None = None
    median_days_listed: float | None = None
    sell_through_pct: float
    price_drop_pct: float


class AgencyBehaviorOut(BaseModel):
    """Aggregated pricing and discounting behavior metrics for a real estate agency."""
    agency: str
    sample: int
    price_drop_pct: float
    median_drop_pct: float | None = None
    # positive = lists above the local median €/sqm
    median_sqm_price_delta_pct: float | None = None
    priced_sample: int
    median_days_to_gone: float | None = None


class MarketVelocityOut(BaseModel):
    """Comprehensive API response detailing area velocities and agency pricing signatures."""
    contract: str
    city: str
    generated_at: datetime
    min_sample: int
    total_properties: int
    closed_properties: int
    # start of the observation window: no days-on-market value can exceed it
    tracking_since: datetime | None = None
    areas: list[AreaVelocityOut] = []
    agencies: list[AgencyBehaviorOut] = []
