"""Pydantic schemas for REST API input/output."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field, field_validator, model_validator


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


class CommuteOut(BaseModel):
    """One routed leg from a property to one of the user's saved places, as
    shown on its card. Distance and duration are OSRM's raw metres and seconds:
    the UI does the rounding, so a future "42 min" and "0.7 km" are one
    formatting decision rather than a wire format that has already lost the
    precision."""

    name: str
    mode: str  # car | foot | bike
    distance_m: float
    duration_s: float


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
    # where that pin came from: "portal" / "address" are the property's own
    # location, "zone" / "city" are the middle of an area it is somewhere
    # inside. Served rather than inferred on the client, because the difference
    # is a fact the backend established and the map must not redraw as if the
    # two were the same thing (services/geocoder.py).
    coordinate_source: str = ""
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
    # The OMI band for the same zone (services/omi_benchmark.py): min/max €/sqm
    # from *recorded transactions*, and the semester they were recorded in. A
    # separate pair of fields on purpose — the client shows the two benchmarks
    # side by side, each labelled with what it is, and never merges them
    # (invariant 22). All null when nothing is imported or the property was
    # never placed in a zone.
    omi_min_sqm_price: float | None = None
    omi_max_sqm_price: float | None = None
    omi_semester: str | None = None
    # True once that semester's window has been closed longer than
    # `omi_benchmark.STALE_AFTER_MONTHS`. Served rather than derived on the
    # client so the dashboard and the print dossier age the data by one rule.
    omi_stale: bool = False
    omi_zone_code: str = ""  # persisted; the micro-zone the band belongs to
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
    # Travel time to the user's saved places (services/commute.py). Empty when
    # the feature is off, when the property has no pin, or when the leg has not
    # been routed yet — the annotation is cache-only, so an unrouted card simply
    # shows no commute rather than blocking the page on a routing request.
    commutes: list[CommuteOut] = []

    @field_validator("found_by", "commutes", mode="before")
    @classmethod
    def _empty_when_unannotated(cls, v: object) -> object:
        # The transient Property.found_by / .commutes are None until
        # routers.selection.annotate_provenance and services.commute.annotate_commutes
        # run; from_attributes would then validate None against a list type and
        # fail. Any path that serializes an unannotated property degrades to
        # "nothing to show" rather than a 500.
        return v or []


class ListingAuditOut(BaseModel):
    """What the optional model read in one listing's text
    (services/listing_auditor.py).

    Deliberately not part of `PropertyOut`: an audit exists only for the
    properties the user asked about, so carrying it on every grid row would be
    a join for a field almost every card leaves empty. The detail modal fetches
    it on its own.

    `cached` says the answer came from the stored row rather than the model,
    and `stale` that the ad has been rewritten since it was written — both are
    printed, because an audit is only as good as the text it read.
    """

    summary: str = ""
    condition: str = "unknown"  # new | renovated | good | to_renovate | unknown
    tenant: str = "unknown"  # yes | no | unknown — sold with a sitting tenant
    costs: list[str] = []  # what the asking price does not include
    concerns: list[str] = []  # weak points the text admits to
    negotiation: list[str] = []  # facts usable when making an offer
    model: str = ""
    created_at: datetime
    cached: bool = False
    stale: bool = False


class PropertyPage(BaseModel):
    """One window of the filtered property set, plus the size of the whole.

    `total` is what the dashboard counts and what tells the infinite scroll
    whether another page exists — it is the size of the filtered set, not of
    `items`. Keep `frontend/src/types/index.ts` (`PropertyPage`) in step with
    this shape.
    """

    items: list[PropertyOut]
    total: int
    limit: int | None
    offset: int


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


class ScanProgressOut(BaseModel):
    """What the scan in flight is doing right now (`scanner.get_scan_progress`).

    `total_pages` and `total_listings` are `None` unless the portal itself
    declared them, and that is the whole contract with whatever draws this: a
    proportion may only be shown against a real total, and every other case is a
    count that rises. A bar filling to 90% and stopping teaches the user the app
    lies, so the shape refuses to make one possible.
    """

    active: bool = False
    # idle | starting | fetching | waiting | saving | locating
    phase: str = "idle"
    detail: str = ""
    profile: str = ""
    profile_index: int = 0
    profile_total: int = 0
    portal: str = ""
    page: int = 0
    total_pages: int | None = None
    listings: int = 0
    total_listings: int | None = None
    transport: str = ""
    waiting_seconds: float = 0.0


class ScanJournalEntryOut(BaseModel):
    """One search's line in the scan journal (`scanner.get_scan_journal`)."""

    profile_id: int | None = None
    profile: str = ""
    portal: str = ""
    started_at: str = ""
    finished_at: str = ""
    pages: int = 0
    listings: int = 0
    outcome: str = ""  # ok | no_results | blocked | error, as ScrapeResult said
    detail: str = ""
    transport: str = ""
    stopped_because: str = ""


class ScraperStatusOut(BaseModel):
    """The dashboard's poll: `scan_state`, the schedule, and the live progress."""

    running: bool = False
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_summary: str = ""
    next_auto_run: str | None = None
    paused: bool = False
    data_version: str = ""
    progress: ScanProgressOut = ScanProgressOut()


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
            raise ValueError("The URL must come from immobiliare.it or idealista.it")
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
    # `zone` is the first of `zones`, kept while the form still reads one string.
    zone: str = ""
    zones: list[str] = []
    # The portal's own zone keys, as they appear in the URL the user pasted
    # (Immobiliare's `idMZona[]`, Idealista's opaque `/multi/` ids). Exact where
    # a slug is best-effort, and sometimes the only thing a multi-zone URL
    # carries: a selection made on the portal's map keeps the path at the bare
    # municipality, so ids present with no names is the normal case, not an
    # edge one. A field the parser could not name shows its ids rather than
    # nothing — see search_builder.
    zone_ids: list[str] = []
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
    floor: str = ""  # ground | middle | top
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
    telegram_actions_enabled: bool | None = None
    email_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    email_from: str | None = None
    email_to: str | None = None
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
    split_large_searches: bool | None = None
    health_alert_after_failures: int | None = None
    proxy_url: str | None = None
    proxy_urls: list[str] | None = None
    scrape_api_provider: str | None = None
    scrape_api_key: str | None = None
    scrape_api_mode: str | None = None
    transport_escalate_after_failures: int | None = None
    idealista_api_key: str | None = None
    idealista_api_secret: str | None = None
    idealista_api_max_pages: int | None = None
    nominatim_url: str | None = None
    commute_enabled: bool | None = None
    commute_points: list[dict] | None = None
    osrm_url: str | None = None
    nl_parser_backend: str | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    listing_audit_enabled: bool | None = None
    datadome_cookie: str | None = None
    datadome_auto_refresh: bool | None = None
    datadome_cookie_ttl_minutes: int | None = None
    availability_browser_first: bool | None = None
    availability_browser_headful: bool | None = None
    browser_engine: str | None = None
    browser_humanize: bool | None = None
    tls_impersonations: list[str] | None = None
    repair_agency_prefixes: list[str] | None = None
    api_auth_token: str | None = None

    @field_validator("health_alert_after_failures")
    @classmethod
    def failures_not_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("must be >= 0 (0 disables health alerting)")
        return v

    @field_validator("idealista_api_max_pages")
    @classmethod
    def api_pages_at_least_one(cls, v: int | None) -> int | None:
        # Every page is a metered request against a ceiling nobody publishes, so
        # the floor is 1 rather than a 0 meaning "unlimited".
        if v is not None and v < 1:
            raise ValueError("must be >= 1 (each page is one API request)")
        return v

    @field_validator("scrape_api_provider")
    @classmethod
    def known_scrape_provider(cls, v: str | None) -> str | None:
        if v is not None and v not in ("scrapfly", "scraperapi", "zyte"):
            raise ValueError("must be one of: scrapfly, scraperapi, zyte")
        return v

    @field_validator("scrape_api_mode")
    @classmethod
    def known_scrape_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in ("always", "fallback"):
            raise ValueError("must be one of: always, fallback")
        return v

    @field_validator("nl_parser_backend")
    @classmethod
    def known_nl_backend(cls, v: str | None) -> str | None:
        if v is not None and v not in ("deterministic", "llm"):
            raise ValueError("must be one of: deterministic, llm")
        return v

    @field_validator("dream_max_price", "dream_min_rooms", "dream_min_sqm", "dream_min_floor")
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
    zones: list[str] = []  # the same field at its real arity; `zone` is zones[0]
    zone_ids: list[str] = []  # the portal's own zone keys, exact where a slug is not
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
    floor: str = ""  # ground | middle | top
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

    @model_validator(mode="after")
    def zone_agrees_with_zones(self) -> "SearchBuilderIn":
        """One field, two arities, kept in step.

        The form still posts `zone` and will post `zones` once it is a list, and
        a payload carrying one of them must never mean less than the other:
        `zone` alone left the list empty for whatever reads it next, and `zones`
        alone left `zone` empty — which is the whole municipality on Idealista,
        the wider half of a paired search nobody asked for. Where both arrive,
        the list is the parameter and `zone` is its mirror, so the two can never
        describe different searches.
        """
        from .services.search_builder import zone_id_list, zone_names

        names = zone_names(self.zone, self.zones or None)
        self.zones = names
        self.zone = names[0] if names else ""
        self.zone_ids = zone_id_list(self.zone_ids)
        return self

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


class SearchBuilderUrlsOut(BaseModel):
    """What `search_builder.build_search_urls` actually returns: a URL per
    portal, plus the two pieces of provenance the form shows next to them.

    Spelled out as a model rather than a `dict[str, str]` because it is not
    one — `idealista_zone_page` is a bool and `idealista_unsupported` a list,
    so the looser-looking annotation was in fact the stricter one and rejected
    every real payload.
    """

    immobiliare: str
    idealista: str
    # whether the Idealista URL is its precise zone page (slug confirmed by the
    # portal) rather than the broader free-text search
    idealista_zone_page: bool = False
    # requested filters Idealista's URL grammar cannot express, so its half of
    # the pair is the wider search
    idealista_unsupported: list[str] = []
    # the same admission for Immobiliare's zone selection: which of the zones
    # the user picked the URL about to be saved cannot carry, and why. Said
    # here because after the save the only evidence is a scan that answers
    # normally for a wider area — see search_validator.zone_coverage_warnings
    zone_warnings: list[str] = []


class AssistantSearch(BaseModel):
    """One search alternative the assistant understood. A query with
    disjunctions ("bilocale in zona X o trilocale in zona Y") yields one of
    these per alternative."""

    params: AssistantParams
    # human-readable read-back of the query, shown before anything is saved
    interpretation: list[str] = []
    notes: list[str] = []  # assumptions the parser had to make
    warnings: list[str] = []  # what it could not resolve
    # None when no city was found: a city-less portal URL would silently
    # search all of Italy (see invariant #7)
    urls: SearchBuilderUrlsOut | None = None


class AssistantOut(BaseModel):
    searches: list[AssistantSearch]


class AreaVelocityOut(BaseModel):
    """Aggregated market speed metrics for a specific neighborhood or city."""

    city: str
    zone: str
    scope: str  # "zone" | "city"
    sample: int
    closed: int  # how many left the market ("gone")
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
