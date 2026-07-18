"""Pydantic schemas for REST API input/output."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field, field_validator


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


class TagOut(BaseModel):
    """API response model for a user-defined tag. `count` (usage across
    properties) is populated only by GET /api/tags; when nested inside
    PropertyOut.tags it stays at its default and is not meaningful there."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    count: int = 0


class TagCreate(BaseModel):
    """Payload to create (or reuse, if a case-insensitive match exists) a tag."""
    name: str


class ProfileRef(BaseModel):
    """A monitored search that found a property, as shown on its card: just the
    id (to link back to the search) and its name."""
    id: int
    name: str


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
    source: str = "scan"  # "scan" (monitored search) | "email" (inbox import)
    is_favorite: bool = False
    notes: str = ""
    # market position vs local median €/sqm (computed per request,
    # see services/pricing_stats.py; None when not enough comparables)
    area_median_sqm_price: float | None = None
    area_median_scope: str | None = None  # "zone" | "city"
    sqm_price_delta_pct: float | None = None
    # Smart Match Score: 0–100 compatibility vs "dream home" (None when off)
    match_score: int | None = None
    # Deal Score: congruity vs fair value (positive = below market; None = no data)
    deal_score: int | None = None
    deal_label: str | None = None
    deal_reasons: list[str] | None = None
    expected_discount_pct: float | None = None
    target_price_low: float | None = None
    target_price_high: float | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    sold_at: datetime | None = None  # set when the user marked it sold
    listings: list[ListingOut] = []
    price_history: list[PriceHistoryOut] = []
    tags: list[TagOut] = []
    # Which monitored searches have found this property (provenance, from the
    # ListingProfile links). Empty when unannotated or for a property with no
    # links (e.g. an email import never yet re-found by a scan). See invariant 20.
    found_by: list[ProfileRef] = []

    @field_validator("found_by", mode="before")
    @classmethod
    def _found_by_default(cls, v: object) -> object:
        # The transient Property.found_by is None until main._annotate_provenance
        # runs; from_attributes would then validate None against list[ProfileRef]
        # and fail. Any path that serializes an unannotated property degrades to
        # "no provenance" rather than a 500.
        return v or []


class PropertyPatch(BaseModel):
    """User-curated fields; scans never touch them."""
    is_favorite: bool | None = None
    notes: str | None = None
    # None = don't touch tags; a list is a full replace of the property's tag
    # set (matches a chip-editor UI: read current tags, add/remove client-side,
    # PATCH the final set).
    tag_ids: list[int] | None = None


class PropertyCheckIn(BaseModel):
    """Payload for live availability verification (`AdProbe`) of dashboard properties."""
    ids: list[int]


class PropertyBulkIn(BaseModel):
    """Payload for a bulk action on many selected properties at once."""
    ids: list[int]
    # hide/restore mirror the single-property DELETE/restore; favorite/unfavorite
    # mirror the PATCH is_favorite flag; sold mirrors the mark-sold route —
    # batched so the user can clear a cluttered dashboard (e.g. every "nuova
    # costruzione", or a whole cluster of "VENDUTO" re-posts) in one gesture.
    action: Literal["hide", "restore", "favorite", "unfavorite", "sold", "add_tag", "remove_tag"]
    # required only for "add_tag"/"remove_tag", validated in the route
    tag_id: int | None = None


class PricingTrendPoint(BaseModel):
    """One dated median €/sqm reading for an area."""
    captured_on: date
    median_sqm_price: float
    sample_count: int


class PricingTrendOut(BaseModel):
    """Median €/sqm over time for one (city, zone, contract) area."""
    city: str
    zone: str
    contract: str
    points: list[PricingTrendPoint] = []


class TrendAreaOut(BaseModel):
    """An area with enough snapshot history to plot (>= 2 points)."""
    city: str
    zone: str
    contract: str
    point_count: int


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


class SearchProfileIdsIn(BaseModel):
    """The searches a bulk preview ("what would deleting these cost?") is about."""
    ids: list[int]


class SearchProfileBulkIn(SearchProfileIdsIn):
    """Payload for an action applied to several monitored searches at once.

    `notify_channels` is only read by the "notify" action, `delete_results` only
    by "delete" — the alternative (one endpoint per action) would fork the
    ownership rules the delete depends on across four routes.
    """
    action: Literal["activate", "pause", "notify", "delete"]
    notify_channels: str = ""  # "" = all enabled, CSV = those, "none" = muted
    delete_results: bool = False


class SearchBuilderParamsOut(BaseModel):
    """Parameters extracted from or used to build a portal search URL."""
    city: str = ""
    province: str = ""
    zone: str = ""
    contract: str = "sale"
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: int | None = None
    balcony: bool = False
    garden: bool = False
    parking: bool = False
    elevator: bool = False
    exclude_auctions: bool = False
    pool: bool = False
    floor: str = ""                 # ground | middle | top
    # new | good | excellent | to_renovate — "excellent" is Immobiliare's stato=6
    # and the one condition Idealista has no equivalent for, so it is the only
    # value idealista_unsupported reports.
    condition: str = ""


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

    @computed_field
    @property
    def params(self) -> SearchBuilderParamsOut:
        from .services.search_builder import parse_search_url
        return SearchBuilderParamsOut(**parse_search_url(self.search_url))


class UrlIn(BaseModel):
    """Payload for extracting builder parameters from a URL."""
    url: str


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
    scanning_paused: bool | None = None
    match_score_enabled: bool | None = None
    dream_max_price: int | None = None
    dream_min_rooms: int | None = None
    dream_min_sqm: int | None = None
    dream_min_floor: int | None = None
    dream_keywords: list[str] | None = None
    dream_zones: list[str] | None = None
    excluded_keywords: list[str] | None = None
    request_delay_seconds: float | None = None
    max_pages_per_search: int | None = None
    health_alert_after_failures: int | None = None
    proxy_url: str | None = None
    scrape_api_provider: str | None = None
    scrape_api_key: str | None = None
    nominatim_url: str | None = None
    nl_parser_backend: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    datadome_cookie: str | None = None
    datadome_auto_refresh: bool | None = None
    datadome_cookie_ttl_minutes: int | None = None
    availability_browser_first: bool | None = None
    availability_browser_headful: bool | None = None
    browser_engine: str | None = None
    tls_impersonations: list[str] | None = None
    api_auth_token: str | None = None

    @field_validator("health_alert_after_failures")
    @classmethod
    def failures_not_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("must be >= 0 (0 disables health alerting)")
        return v

    @field_validator("scrape_api_provider")
    @classmethod
    def known_scrape_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("scrapfly", "scraperapi", "zyte"):
            raise ValueError("must be one of: scrapfly, scraperapi, zyte")
        return v

    @field_validator("nl_parser_backend")
    @classmethod
    def known_nl_backend(cls, v: str | None) -> str | None:
        if v is not None and v not in ("deterministic", "llm"):
            raise ValueError("must be one of: deterministic, llm")
        return v

    @field_validator("email_import_auto_scan_interval_hours")
    @classmethod
    def import_interval_at_least_hourly(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("must be >= 1 hour")
        return v

    @field_validator("dream_max_price", "dream_min_rooms", "dream_min_sqm",
                     "dream_min_floor")
    @classmethod
    def dream_fields_not_negative(cls, v: int | None) -> int | None:
        # 0 is the "no constraint" sentinel; a negative is a client bug
        if v is not None and v < 0:
            raise ValueError("must be >= 0 (0 means no constraint)")
        return v


class SearchBuilderIn(BaseModel):
    """Structured parameters the search builder turns into portal URLs."""
    city: str
    province: str = ""
    zone: str = ""  # neighborhood; Immobiliare slugs are best-effort
    contract: str = "sale"  # sale | rent
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: int | None = None
    balcony: bool = False
    garden: bool = False
    parking: bool = False
    elevator: bool = False
    exclude_auctions: bool = False
    pool: bool = False
    floor: str = ""                 # ground | middle | top
    # new | good | excellent | to_renovate — "excellent" is Immobiliare's stato=6
    # and the one condition Idealista has no equivalent for, so it is the only
    # value idealista_unsupported reports.
    condition: str = ""
    # Asks Idealista whether it knows this zone's slug, so the precise zone page
    # can be used instead of the broader free-text search (search_builder.
    # resolve_idealista_url). One live request, hence off unless the user
    # pressed Generate.
    verify: bool = False

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
    image_url: str = ""
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
