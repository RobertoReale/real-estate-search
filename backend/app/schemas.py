"""Pydantic schemas for REST API input/output.

These are also the source of `frontend/src/types/api.ts`: the OpenAPI document
FastAPI derives from them is what `scripts/gen_api_types.py` compiles into the
browser's types. So a field described loosely here is described loosely there,
and the frontend loses a check it used to have — which is why the models that go
*out* say `Literal` where the value is a closed set, and why they inherit from
`ApiOut` below.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field, field_validator, model_validator


class ApiOut(BaseModel):
    """Base for every model this API sends.

    It sets one thing: a field with a default is still **required** in the
    serialized schema. That is simply the truth — Pydantic writes every field on
    the way out, defaulted or not, so a response never omits one — but the
    default JSON Schema marks it optional, and the generated TypeScript then
    types half the payload as `field?: T | null`. Every reader downstream has to
    handle an `undefined` that cannot occur, and the ones that mattered
    (`deal_score`, `sqm_price_delta_pct`, every median) are exactly the numbers
    the UI does arithmetic on.

    Input models deliberately do **not** inherit this: there a default means the
    field may genuinely be left out.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# The closed sets, written once and shared by every model that carries them.
# Each mirrors a vocabulary the backend already fixes in code — the alternative
# is `str` in the document and a hand-written union in the browser that nothing
# keeps in step.
Contract = Literal["sale", "rent"]
# services/geocoder.py: SOURCE_PORTAL / SOURCE_ADDRESS / SOURCE_ZONE, plus "" for
# a pin written before the column existed. There is deliberately no city-wide
# value (see APPROXIMATE_SOURCES).
CoordinateSource = Literal["", "portal", "address", "zone"]
# invariant 19: "email" is historical (the retired inbox import) and upgrade-only
PropertySource = Literal["scan", "email"]
AreaScope = Literal["zone", "city"]
DealLabel = Literal["undervalued", "fair", "overpriced"]
BuilderFloor = Literal["", "ground", "middle", "top"]
BuilderCondition = Literal["", "new", "good", "excellent", "to_renovate"]


class ListingOut(ApiOut):
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


class PriceHistoryOut(ApiOut):
    """API response model recording a historical price variation of a Property."""

    model_config = ConfigDict(from_attributes=True)

    old_price: float | None
    new_price: float
    changed_at: datetime


class TagOut(ApiOut):
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


class ProfileRef(ApiOut):
    """A monitored search that found a property, as shown on its card: just the
    id (to link back to the search) and its name."""

    id: int
    name: str


class CommuteOut(ApiOut):
    """One routed leg from a property to one of the user's saved places, as
    shown on its card. Distance and duration are OSRM's raw metres and seconds:
    the UI does the rounding, so a future "42 min" and "0.7 km" are one
    formatting decision rather than a wire format that has already lost the
    precision."""

    name: str
    # commute.points_from_settings clamps anything else to DEFAULT_MODE, so the
    # set is closed by the time it reaches here
    mode: Literal["car", "foot", "bike"]
    distance_m: float
    duration_s: float


class PropertyOut(ApiOut):
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
    # where that pin came from: "portal" and "address" are the property's own
    # location, "zone" is the middle of the district it is somewhere inside, and
    # "" is a pin from before this column existed. Served rather than inferred on
    # the client, because the difference is a fact the backend established and
    # the map must not redraw as if the two were the same thing
    # (services/geocoder.py).
    coordinate_source: CoordinateSource = ""
    rooms: int | None
    floor: str
    sqm: float | None
    contract: Contract = "sale"
    current_min_price: float | None
    first_price: float | None
    image_url: str
    status: str
    filtered_reason: str
    source: PropertySource = "scan"  # monitored search | the retired inbox import
    is_favorite: bool = False
    notes: str = ""
    # market position vs local median €/sqm (computed per request,
    # see services/pricing_stats.py; None when not enough comparables)
    area_median_sqm_price: float | None = None
    area_median_scope: AreaScope | None = None
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
    deal_label: DealLabel | None = None
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


class ListingAuditOut(ApiOut):
    """What the optional model read in one listing's text
    (services/listing_auditor.py).

    Deliberately not part of `PropertyOut`: an audit exists only for the
    properties the user asked about, so carrying it on every grid row would be
    a join for a field almost every card leaves empty. The detail fetches
    it on its own.

    `cached` says the answer came from the stored row rather than the model,
    and `stale` that the ad has been rewritten since it was written — both are
    printed, because an audit is only as good as the text it read.
    """

    summary: str = ""
    # both clamped by listing_auditor._clean_audit before they are stored: a
    # local model asked for one of five words can answer with a sentence
    condition: Literal["new", "renovated", "good", "to_renovate", "unknown"] = "unknown"
    tenant: Literal["yes", "no", "unknown"] = "unknown"  # sold with a sitting tenant
    costs: list[str] = []  # what the asking price does not include
    concerns: list[str] = []  # weak points the text admits to
    negotiation: list[str] = []  # facts usable when making an offer
    model: str = ""
    created_at: datetime
    cached: bool = False
    stale: bool = False


class PropertyPage(ApiOut):
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


class PricingTrendPoint(ApiOut):
    """One dated median €/sqm reading for an area."""

    captured_on: date
    median_sqm_price: float
    sample_count: int


class PricingTrendOut(ApiOut):
    """Median €/sqm over time for one (city, zone, contract) area."""

    city: str
    zone: str
    contract: Contract
    points: list[PricingTrendPoint] = []


class TrendAreaOut(ApiOut):
    """An area with enough snapshot history to plot (>= 2 points)."""

    city: str
    zone: str
    contract: Contract
    point_count: int


class ScanProgressOut(ApiOut):
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


class ScanJournalEntryOut(ApiOut):
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
    # full | quick — which kind of scan this was. A quick scan stops as soon as
    # a page holds nothing new, so it is fast and it is *partial*; recording
    # which one ran is what keeps the two from being read as the same thing.
    mode: str = "full"


class ScraperStatusOut(ApiOut):
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


class SearchBuilderParamsOut(ApiOut):
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
    contract: Contract = "sale"
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
    # both read off the portals' own fixed vocabularies (search_builder's
    # IMMOBILIARE_FLOORS / IMMOBILIARE_CONDITION and their Idealista twins), so
    # "" is the only other thing the parser can produce
    floor: BuilderFloor = ""
    # "excellent" is Immobiliare's stato=6 and the one condition Idealista has no
    # equivalent for, so it is the only value idealista_unsupported reports.
    condition: BuilderCondition = ""


class SearchProfileOut(ApiOut):
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
    scan_portals_concurrently: bool | None = None
    stop_when_nothing_new: bool | None = None
    full_sweep_every_days: int | None = None
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


class AssistantParams(ApiOut):
    """What the parser understood: same shape as SearchBuilderIn, except
    `city` may be empty (the parser could not identify one)."""

    city: str = ""
    province: str = ""
    zone: str = ""
    contract: Contract = "sale"
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: int | None = None


class SearchBuilderUrlsOut(ApiOut):
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


class AssistantSearch(ApiOut):
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


class AssistantOut(ApiOut):
    searches: list[AssistantSearch]


class AreaVelocityOut(ApiOut):
    """Aggregated market speed metrics for a specific neighborhood or city."""

    city: str
    zone: str
    scope: AreaScope
    sample: int
    closed: int  # how many left the market (inferred "gone" + confirmed "sold")
    # of those, the ones the user confirmed sold. Declared, not inferred: the
    # service has always computed it, and a field the response model does not
    # name is a field the response model deletes.
    sold: int = 0
    median_days_to_gone: float | None = None
    median_days_to_sold: float | None = None  # the confirmed-sale subset
    median_days_listed: float | None = None
    sell_through_pct: float
    price_drop_pct: float


class AgencyBehaviorOut(ApiOut):
    """Aggregated pricing and discounting behavior metrics for a real estate agency."""

    agency: str
    sample: int
    price_drop_pct: float
    median_drop_pct: float | None = None
    # positive = lists above the local median €/sqm
    median_sqm_price_delta_pct: float | None = None
    priced_sample: int
    median_days_to_gone: float | None = None


class MarketVelocityOut(ApiOut):
    """Comprehensive API response detailing area velocities and agency pricing signatures."""

    contract: Contract
    city: str
    generated_at: datetime
    min_sample: int
    total_properties: int
    closed_properties: int
    sold_properties: int = 0  # confirmed sales within closed_properties
    # start of the observation window: no days-on-market value can exceed it
    tracking_since: datetime | None = None
    areas: list[AreaVelocityOut] = []
    agencies: list[AgencyBehaviorOut] = []


# --- Answers that used to be anonymous dictionaries ---
#
# Everything below describes a response the routers already returned; declaring
# it changes no payload. What it changes is that the shape now exists in the
# OpenAPI document, which is where `frontend/src/types/api.ts` is generated
# from — an undeclared route publishes an empty schema, and an empty schema is
# what let the frontend keep a hand-written twin that nothing checked. Two of
# them had already drifted (`sold_properties` above; `approximate` below).


class OkOut(ApiOut):
    """An action whose entire result is "it was done" — the cancels, the
    notification tests, hiding a property. `ok` is always true: anything that
    did not happen leaves as an HTTP error, never as `ok: false`."""

    ok: bool = True


class ClearedOut(ApiOut):
    """How many cached rows a "forget these" action removed."""

    cleared: int


class BulkActionOut(ApiOut):
    """A bulk action over selected properties: how many of the ids actually
    existed. Missing ids are skipped, so `processed` is the honest count."""

    ok: bool = True
    processed: int


class AvailabilityCheckSummaryOut(ApiOut):
    """What one run of the availability check found.

    `unknown` is the load-bearing one: a portal that refused to answer (a block,
    a timeout) leaves the property untouched and lands here, never in `gone`
    (invariant 16).
    """

    checked: int = 0
    gone: int = 0
    online: int = 0
    unknown: int = 0
    # the portal refused three times in a row and the batch stopped early
    aborted: bool = False
    # the per-run live-fetch budget ran out: re-run to continue where it stopped
    capped: bool = False
    # the user pressed Stop — distinct from `aborted`, so the UI does not show a
    # block warning for a deliberate stop
    cancelled: bool = False
    last_error: str | None = None
    # how many times a fresh DataDome cookie was grabbed mid-check to recover
    cookie_refreshed: int = 0
    # human-readable transport diagnostic: "fast requests (curl)",
    # "chromium (visible window)", "browser off: no option enabled", …
    transport: str = ""


class AvailabilityCheckProgressOut(ApiOut):
    """The running availability check, as the progress bar polls it."""

    active: bool = False
    done: int = 0
    total: int = 0
    gone: int = 0
    online: int = 0
    unknown: int = 0
    last_error: str | None = None
    transport: str = ""


class PropertyCheckOut(ApiOut):
    """One property probed on demand: the card as it now stands, and the same
    summary the batch answers with."""

    property: PropertyOut
    summary: AvailabilityCheckSummaryOut


class PropertyGeocodeOut(ApiOut):
    """One property geocoded on demand. `located` is the whole answer: a lookup
    the address was too vague to resolve is not an error (fail-open), so the
    property comes back unchanged with `located: false`."""

    property: PropertyOut
    located: bool


class GeocodeProgressOut(ApiOut):
    """The running geocoding batch, as the progress bar polls it."""

    active: bool = False
    done: int = 0
    total: int = 0
    geocoded: int = 0
    cached: int = 0
    not_found: int = 0
    remaining: int = 0
    last_error: str | None = None


class GeocodeSummaryOut(ApiOut):
    """What one geocoding batch achieved."""

    scanned: int = 0
    geocoded: int = 0
    # of those, how many landed on a district centre rather than a street.
    # "40 properties placed" and "40 properties placed, 31 of them only to the
    # district" are different answers, and only one of them is honest.
    approximate: int = 0
    cached: int = 0
    not_found: int = 0
    remaining: int = 0
    cancelled: bool = False


class CommuteProgressOut(ApiOut):
    """The running commute batch, as the progress bar polls it."""

    active: bool = False
    done: int = 0
    total: int = 0
    routed: int = 0
    cached: int = 0
    unreachable: int = 0
    remaining: int = 0
    last_error: str | None = None


class CommuteSummaryOut(ApiOut):
    """What one commute batch achieved. `points` is how many saved places it
    routed against, so a run that found nothing can say whether that is because
    there was nowhere to route to."""

    scanned: int = 0
    routed: int = 0
    cached: int = 0
    unreachable: int = 0
    remaining: int = 0
    points: int = 0
    cancelled: bool = False


class ScraperHealthDayOut(ApiOut):
    """One day's scraping counters for one portal."""

    date: str  # ISO date
    attempts: int = 0
    successes: int = 0
    blocked: int = 0
    errors: int = 0


class ScraperHealthPortalOut(ApiOut):
    """One portal over the window: its daily series and the totals behind the
    block rate."""

    portal: str
    days: list[ScraperHealthDayOut] = []
    last_transport: str = ""
    attempts: int = 0
    failures: int = 0
    block_rate: float = 0.0  # 0..1 over the window


class ScraperHealthProfileOut(ApiOut):
    """One active search's live failure streak (invariant 11's counter)."""

    profile_id: int
    name: str
    portal: str
    consecutive_failures: int = 0
    last_run_status: str = ""


class ScraperHealthOut(ApiOut):
    """The scraping-health panel: per-portal history, per-search streaks, and
    the transport the next scan would start on."""

    window_days: int
    portals: list[ScraperHealthPortalOut] = []
    profiles: list[ScraperHealthProfileOut] = []
    transport: str = ""


class ScanTriggerOut(ApiOut):
    """Whether the manual trigger started a scan or found one already running."""

    status: str  # started | already_running


class ProfileResultsOut(ApiOut):
    """What a set of searches has produced in the dashboard, and what deleting
    them would take with it. `tracked` counts only properties whose provenance
    is recorded: cards from before that tracking existed are not attributable
    and stay (invariant 20)."""

    tracked: int
    deletable: int
    kept_shared: int  # also found by a search outside the selection
    kept_curated: int  # favourited or annotated by hand: never deleted in bulk


class ProfileDeletedResultsOut(ProfileResultsOut):
    """The same classification, after the delete ran, plus how many portal ads
    went with the properties."""

    listings: int


class ProfileBulkOut(ApiOut):
    """A bulk action over selected searches. `results` is filled only by the
    "delete" action, and only when the results were deleted too."""

    ok: bool = True
    processed: int
    results: ProfileDeletedResultsOut | None = None


class BackupFileOut(ApiOut):
    """One copy of the database in the backups folder.

    `kind` is what the copy is there for, and it decides what the row says:
    `daily` is one of the fourteen rotating copies, `pre-upgrade` is the state a
    version change left behind (kept indefinitely), `imported` is a database
    brought in from another install. `revision` is the schema it holds — null
    when the file is too damaged to say, which is exactly when the user needs to
    see the row rather than a gap.
    """

    name: str
    kind: Literal["daily", "pre-upgrade", "imported"]
    size_bytes: int
    taken_at: str
    revision: str | None = None


class BackupListOut(ApiOut):
    """The copies on disk, newest first, and the folder holding them — a real
    path on the user's machine, which is what makes them usable outside this
    app."""

    folder: str
    backups: list[BackupFileOut] = []


class BackupRestoreOut(ApiOut):
    """A completed restore: which copy went live, and the copy of the *previous*
    state taken first, so restoring the wrong file is recoverable."""

    restored: str
    backup: str | None = None


class ResetOut(ApiOut):
    """A scoped data reset: what was cleared, and how many rows of each. Only
    the factory reset takes a snapshot first, so only it fills `backup`."""

    scope: str  # dashboard | pricing-snapshots | factory
    deleted: dict[str, int] = {}
    backup: str | None = None


class RestartOut(ApiOut):
    """`reload` says which path the restart took: true = the file watcher owns
    the respawn, false = the process re-exec'd itself."""

    ok: bool = True
    reload: bool


class LogTailOut(ApiOut):
    """The tail of the backend's own log, and where that file lives."""

    lines: list[str] = []
    path: str


class DatadomeRefreshOut(ApiOut):
    """A cookie grab that succeeded. Only the first characters of the cookie
    come back: the value itself is a credential and never leaves the backend."""

    ok: bool = True
    portal: str
    updated_at: str
    cookie_preview: str


class InstallOut(ApiOut):
    """One of the optional-browser installers, with the line to show the user."""

    ok: bool = True
    message: str


class CommutePointOut(ApiOut):
    """A place the user commutes to, as stored in the settings: either an
    address (geocoded once, then remembered) or an explicit pin."""

    name: str = ""
    address: str = ""
    lat: float | None = None
    lng: float | None = None
    mode: str = "car"  # car | foot | bike


class SettingsOut(ApiOut):
    """`settings.json` as the dashboard reads it back.

    Every secret is masked here and answered with a `*_set` boolean beside it,
    so the UI can say "configured" without ever holding the value — and so a
    form posting the mask straight back means "keep the stored one" rather than
    "erase it" (see `routers/settings.py`). The two `*_available` flags are not
    stored at all: they are what the backend detected about this machine, so the
    UI offers "install it for me" instead of a field the user cannot fill.

    The fields themselves are `config.DEFAULT_SETTINGS`, and each one's reason
    for existing is written there rather than repeated here.
    """

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False
    telegram_actions_enabled: bool = True
    telegram_token_set: bool = False
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_password_set: bool = False
    email_from: str = ""
    email_to: str = ""
    scan_interval_minutes: int = 60
    scanning_paused: bool = False
    match_score_enabled: bool = False
    dream_max_price: int = 0
    dream_min_rooms: int = 0
    dream_min_sqm: int = 0
    dream_min_floor: int = 0
    dream_keywords: list[str] = []
    dream_zones: list[str] = []
    nominatim_url: str = ""
    geocode_after_scan: bool = True
    commute_enabled: bool = False
    commute_points: list[CommutePointOut] = []
    osrm_url: str = ""
    nl_parser_backend: str = "deterministic"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_api_key_set: bool = False
    llm_model: str = ""
    listing_audit_enabled: bool = False
    excluded_keywords: list[str] = []
    request_delay_seconds: float = 6.0
    max_pages_per_search: int = 10
    split_large_searches: bool = True
    scan_portals_concurrently: bool = True
    stop_when_nothing_new: bool = True
    full_sweep_every_days: int = 7
    health_alert_after_failures: int = 3
    proxy_url: str = ""
    proxy_urls: list[str] = []
    scrape_api_provider: str = "scrapfly"
    scrape_api_key: str = ""
    scrape_api_key_set: bool = False
    scrape_api_mode: str = "fallback"
    transport_escalate_after_failures: int = 2
    idealista_api_key: str = ""
    idealista_api_key_set: bool = False
    idealista_api_secret: str = ""
    idealista_api_secret_set: bool = False
    idealista_api_max_pages: int = 1
    tls_impersonations: list[str] = []
    datadome_cookie: str = ""
    datadome_cookie_set: bool = False
    datadome_auto_refresh: bool = False
    datadome_cookie_updated_at: str = ""
    datadome_cookie_ttl_minutes: int = 50
    datadome_harvester_available: bool = False
    availability_browser_first: bool = False
    availability_browser_headful: bool = False
    browser_engine: str = "auto"
    camoufox_available: bool = False
    browser_humanize: bool = True
    repair_agency_prefixes: list[str] = []
    omi_input_dir: str = ""
    api_auth_token: str = ""
