"""ORM Models: Property (deduplicated real estate property), Listing (portal ad),
PriceHistory (price variations), SearchProfile (monitored search URL)."""

from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# Plain association table (no payload beyond the two FKs, unlike ListingProfile):
# a property can carry any number of user-defined tags and a tag can be reused
# across properties.
property_tags = Table(
    "property_tags",
    Base.metadata,
    Column("property_id", ForeignKey("properties.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Property(Base):
    __tablename__ = "properties"
    # allows the transient (non-mapped) fields below, set only in-process by
    # pricing_stats.annotate_market_position() and never persisted
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="", index=True)
    zone: Mapped[str] = mapped_column(String, default="")
    address: Mapped[str] = mapped_column(String, default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Where the pin above came from, because not every pin means the same thing:
    #
    #   "portal"  the ad itself carried the coordinates — exact, and free
    #   "address" a geocoder lookup of this property's own street — exact
    #   "zone"    the middle of its district, not its address — APPROXIMATE
    #   ""        no pin, or one written before this column existed
    #
    # "zone" is the reason the column exists. A district centroid drawn the same
    # way as a street address is an approximation presented as a location, which
    # is the one kind of wrong the user cannot detect for themselves — so it is
    # recorded here and rendered differently on the map. There is deliberately
    # no comune-wide value: see `geocoder.APPROXIMATE_SOURCES`, which is the
    # single list of which sources are approximate and the only place that
    # judgement is made.
    coordinate_source: Mapped[str] = mapped_column(String, default="")
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor: Mapped[str] = mapped_column(String, default="")
    sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # sale | rent — set from the search URL of the profile that first found it.
    # Kept on the Property (not just the Listing) because dedup must never
    # merge a rental ad with a sale ad of the same physical house.
    contract: Mapped[str] = mapped_column(String, default="sale", index=True)
    current_min_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str] = mapped_column(String, default="")
    # active   = currently for sale
    # filtered = excluded by keyword filter (visible under "Filtered")
    # gone     = not seen by any scan for several days (inferred market exit)
    # hidden   = manually hidden by user (never returns to active automatically)
    # sold     = user confirmed the property was sold/rented out. Like "hidden"
    #            it is a user choice a scan never reverts (invariant 5), but it
    #            is kept as a *confirmed* market close feeding market_velocity —
    #            "gone" is only inferred exit, this is proof (see sold_at).
    status: Mapped[str] = mapped_column(String, default="active")
    filtered_reason: Mapped[str] = mapped_column(String, default="")
    # True when the last scan that saw this property found it *outside* the area
    # its search asked the portal for — a listing the portal filed under the next
    # district, or one it returned from a neighbouring comune altogether. Asking
    # for a zone is not the same as getting one: the portal decides, and it
    # sometimes decides differently.
    #
    # A flag and not a deletion, deliberately. A listing on a zone boundary is
    # often exactly the one the user wants, and dropping it would turn a visible
    # annoyance into an invisible one — so the data keeps it, `scanner`'s summary
    # counts it, and hiding it is a view's choice rather than the scan's.
    # `scanner._outside_requested_area` writes it, and only when it can actually
    # tell: a listing the check cannot place is left exactly as it was, so a
    # search that names no location never marks anything.
    outside_requested_area: Mapped[bool] = mapped_column(Boolean, default=False)
    # how this property first entered the dashboard:
    #   scan  = found by a monitored search profile
    #   email = imported from the inbox (never yet matched by a monitored scan)
    # An email-origin property is upgraded to "scan" the moment a monitored
    # scan re-finds it (see deduplicator.upsert_listing), so "email" means
    # "only ever seen via the inbox" — the set the user wants to prune in bulk.
    source: Mapped[str] = mapped_column(String, default="scan", index=True)
    # user-curated fields: never touched by scans
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    # free-form user categories ("senza ascensore", "con giardino", ...): a
    # property can carry several, a tag can be reused across properties. Like
    # is_favorite/notes above, curated by the user alone — no scan/dedup path
    # touches this relationship.
    tags: Mapped[list["Tag"]] = relationship(secondary=property_tags)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # when the property was marked "gone": the end of its days-on-market
    # window. Nullable because it only exists for gone properties (and for
    # rows marked gone before this column existed: market_velocity falls
    # back to last_seen_at for those).
    gone_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # when the user marked the property "sold": the end of its days-on-market
    # window and, unlike gone_at, a *confirmed* sale date. Nullable (only set
    # once the user marks it). Additive column, auto-migrates.
    sold_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Which OMI micro-zone this property's coordinates fall in — the pair, not
    # just the zone, because `B12` is only unique inside one comune (the same
    # join `OmiQuotation` is keyed by). Empty means "not placed": no coordinates
    # yet, or a pin that falls in no imported zone. Both are ordinary and
    # neither is an error — no zone simply means no OMI benchmark.
    #
    # **Persisted, and filled only by the user-triggered batch**
    # (`services/omi_zones.resolve_property_zones`). Storing the answer is what
    # lets a grid page read it as a plain column; resolving it on read would put
    # ray casting over hundreds of vertices inside every render, which is the
    # same rule that keeps `annotate_commutes` cache-only.
    omi_municipality_code: Mapped[str] = mapped_column(String, default="")
    omi_zone_code: Mapped[str] = mapped_column(String, default="")

    # ordered by id like price_history: the notifier and the exports read
    # listings[0].url as "the primary listing", which without order_by is
    # whatever the database happens to return
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="Listing.id",
    )
    # ordered by id: the scanner reads price_history[-1] as the "latest
    # recorded change", and without order_by the order would not be guaranteed
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        order_by="PriceHistory.id",
    )

    # Transient, request-scoped fields set by pricing_stats.annotate_market_position()
    # and match_score.annotate_match_scores(), read by PropertyOut: never
    # persisted, so plain attributes rather than mapped columns.
    area_median_sqm_price: float | None = None
    area_median_scope: str | None = None
    sqm_price_delta_pct: float | None = None
    # The OMI band of the zone above, set by omi_benchmark.annotate_omi_benchmark:
    # min/max €/sqm the Agenzia delle Entrate records *transactions* at, and the
    # semester it recorded them in. Transient like the median beside it — the
    # figures live in OmiQuotation, and a copy here would go stale on the next
    # import. **Never mixed with the median and never substituted for it**
    # (invariant 22): one is what sellers ask, the other what deeds say.
    omi_min_sqm_price: float | None = None
    omi_max_sqm_price: float | None = None
    omi_semester: str | None = None
    # Whether that semester's period ended long enough ago to stop being current
    # (omi_benchmark.is_stale). Derived from omi_semester rather than stored with
    # it, so the rule lives in one place and every renderer marks the same bands.
    omi_stale: bool = False
    # Smart Match Score: compatibility % vs the user's "dream home" (None = off)
    match_score: int | None = None
    # Deal Score: congruity vs fair value (~[-50, +50]; positive = below market),
    # set by services/deal_score.annotate_deal_scores. All transient.
    deal_score: int | None = None
    deal_label: str | None = None  # "undervalued" | "fair" | "overpriced"
    deal_reasons: list[str] | None = None
    expected_discount_pct: float | None = None
    target_price_low: float | None = None
    target_price_high: float | None = None
    # Which monitored searches have found this property (via its listings'
    # ListingProfile links): a list of {"id", "name"} dicts, set request-scoped
    # by routers.selection.annotate_provenance and read by PropertyOut.found_by. Transient
    # like the annotations above — provenance lives in ListingProfile, this is
    # just the per-request read of it for the card/modal. None = not annotated.
    found_by: list[dict] | None = None
    # Travel time and distance to the user's saved places (work, university,
    # metro), a list of {"name", "mode", "distance_m", "duration_s"} dicts set
    # request-scoped by services/commute.annotate_commutes and read by
    # PropertyOut.commutes. Transient like the annotations above; the routed
    # legs themselves live in CommuteCache. None = not annotated.
    commutes: list[dict] | None = None

    # The optional LLM reading of this property's listing text, once the user
    # has asked for one (services/listing_auditor.py). Cascades like the
    # listings and the price history: an audit outliving its property is
    # garbage no screen can reach.
    audit: Mapped["PropertyAudit | None"] = relationship(
        back_populates="property",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    portal: Mapped[str] = mapped_column(String, index=True)  # immobiliare | idealista
    portal_id: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    agency: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    property: Mapped[Property] = relationship(back_populates="listings")
    # deleting a Listing must not leave its provenance rows behind
    profile_links: Mapped[list["ListingProfile"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class ListingProfile(Base):
    """Which monitored searches have found a given portal ad.

    Many-to-many on purpose: two overlapping searches ("Milano 2-3 locali" and
    "Milano Navigli") legitimately return the same ad, so a single profile_id
    on Listing would have to pick one and lie about the other. Deleting a
    profile "with its results" then has an exact answer: a property is that
    profile's alone only when none of its listings is linked to another one.

    Written by deduplicator.upsert_listing on every scan (not only on the first
    sighting), so a search that starts covering an already-tracked ad is
    recorded the next time it runs. Rows predating this table simply have no
    link: the purge leaves them alone rather than guessing (see data_reset).
    """

    __tablename__ = "listing_profiles"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id"), primary_key=True, index=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    listing: Mapped[Listing] = relationship(back_populates="profile_links")
    profile: Mapped["SearchProfile"] = relationship(back_populates="listing_links")


class Tag(Base):
    """A user-defined free-form category ("senza ascensore", "con giardino", ...),
    attached to any number of Properties via property_tags. `name_normalized`
    (stripped/lowercased) enforces case-insensitive uniqueness so retyping an
    existing tag with different casing reuses it instead of creating a
    near-duplicate; `name` keeps the user's original casing for display."""

    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    name_normalized: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PropertyAudit(Base):
    """One LLM reading of a property's listing text (services/listing_auditor.py).

    Kept rather than recomputed because the answer is the expensive half while
    its input barely moves — the same memory trick as GeocodeCache and
    CommuteCache. `text_digest` is what makes that safe: it is the sha256 of the
    exact text that was sent, so an ad rewritten or re-priced since is read
    again instead of being answered from a row about text nobody can see any
    more. `model` belongs to that identity too, since a different model is a
    different answer.

    The findings live in `payload` as the JSON the service already validated,
    not as a column each: they are lists of free text whose shape belongs to
    `listing_auditor._clean_audit`, nothing filters or sorts on them, and they
    are read back whole by the one card that asked for them.
    """

    __tablename__ = "property_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), unique=True, index=True)
    text_digest: Mapped[str] = mapped_column(String, default="")
    model: Mapped[str] = mapped_column(String, default="")
    payload: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    property: Mapped[Property] = relationship(back_populates="audit")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    old_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_price: Mapped[float] = mapped_column(Float)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    property: Mapped[Property] = relationship(back_populates="price_history")


class PricingSnapshot(Base):
    """One daily median €/sqm reading for an area, kept so the dashboard can
    plot how prices move over time.

    `pricing_stats` computes medians *instantaneously* from the current active
    listings — nothing in the DB remembers what the median was last month. This
    table is that memory: at most one row per (day, city, zone, contract),
    written when a scan completes (or by the daily scheduler job). `zone=""`
    holds the whole-city aggregate. City/zone are stored normalized (lowercased)
    exactly as the median keys are, so the trends query matches without guessing.
    """

    __tablename__ = "pricing_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    captured_on: Mapped[date] = mapped_column(Date, index=True)
    city: Mapped[str] = mapped_column(String, index=True)
    zone: Mapped[str] = mapped_column(String, default="")  # "" = whole city
    contract: Mapped[str] = mapped_column(String, default="sale")
    median_sqm_price: Mapped[float] = mapped_column(Float)
    sample_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ScraperHealthSnapshot(Base):
    """One day of scraping outcomes per portal, accumulated scan by scan.

    The anti-bot pipeline degrades silently: a blocked scraper produces no
    listings, which looks exactly like a quiet market (the same blindness that
    motivated the per-profile health streak, invariant 11 — but the streak only
    knows the *current* outage, not the trend). Each completed profile scan
    increments today's row for its portal, so the dashboard can plot block-rate
    over time and say which transport carried the last success. This is what
    tells the user *when* to add proxies or a scrape-API key, before scans
    "mysteriously stop finding listings".
    """

    __tablename__ = "scraper_health_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    captured_on: Mapped[date] = mapped_column(Date, index=True)
    portal: Mapped[str] = mapped_column(String, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    successes: Mapped[int] = mapped_column(Integer, default=0)
    blocked: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    # human-readable label of the transport the *last* scan of the day used
    # ("local (curl_cffi)", "managed scrape API", ...), for the health panel
    last_transport: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GeocodeCache(Base):
    """One resolved (or unresolved) geocoding lookup, keyed by its query string.

    ~70% of Immobiliare listings arrive with no coordinates, so the map is
    mostly empty. The opt-in geocoder (services/geocoder.py) turns their
    "address/zone + city" into pins — but the free Nominatim endpoint allows one
    request per second, so re-querying the same "via Dante, Milano" on every run
    would make a batch unusable. This table is the memory that keeps it inside
    that limit: a row exists once a query has been tried, and a NULL lat/lng is a
    negative result cached on purpose (do not ask again). Never a source of a
    *wrong* pin — a failed lookup leaves the property's coordinates untouched.
    """

    __tablename__ = "geocode_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String, unique=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CommuteCache(Base):
    """One routed leg — a property's pin to one of the user's saved places, on
    one travel mode — keyed by `leg` (see `services/commute.py` `cache_key`).

    The same memory trick as `GeocodeCache`, for the same reason: the public
    OSRM server is a courtesy, and re-routing every card to every saved place on
    every grid render would abuse it (and stall the page while doing so). A row
    exists once a leg has been routed, and a NULL distance/duration is a
    *negative* answer cached on purpose — OSRM looked and found no way through,
    so there is nothing to gain by asking again. A leg that failed in transport
    (a timeout, a 5xx) is deliberately NOT stored, so the next batch retries it.
    """

    __tablename__ = "commute_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    leg: Mapped[str] = mapped_column(String, unique=True, index=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OmiQuotation(Base):
    """One OMI price band: min/max €/m² for a single (zone, property type,
    conservation state, contract) in one semester.

    The reason this table exists is that every other price judgement in this app
    is circular. The "area median" a listing is compared against is the median of
    the asking prices this app itself scraped, so a uniformly overpriced zone
    reads as fair and the app says nothing. These figures come from the Agenzia
    delle Entrate's Osservatorio del Mercato Immobiliare and are derived from
    **recorded transactions**, which makes them the one reference here that does
    not depend on what sellers are asking. They are not interchangeable with the
    listing median for exactly that reason, and must never be averaged with it.

    Imported from a file the owner downloads once a semester
    (`services/omi_import.py`); the app never fetches them, because the supply
    sits behind an authenticated SPID session. Two semesters coexist and the
    newest wins at lookup — `latest_semester` orders them numerically, since
    "2025/2" and "2025/10" would not sort as text if the format ever grew.

    Indexed on (municipality_code, zone_code) because that is the pair a lookup
    starts from: `municipality_code` is the national comune code (`F205` for
    Milan), which is also what the zone perimeters are keyed by.
    """

    __tablename__ = "omi_quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "YYYY/N" (N = 1 or 2), read from the file's title line — the data rows
    # carry no semester of their own.
    semester: Mapped[str] = mapped_column(String, index=True)
    # National comune code (Comune_amm), NOT the ISTAT one: it is what the KML
    # perimeters use, so it is the half of the join key that has to match.
    municipality_code: Mapped[str] = mapped_column(String, index=True)
    municipality: Mapped[str] = mapped_column(String, default="")
    zone_code: Mapped[str] = mapped_column(String, index=True)
    # Only the zone file carries the description ("CENTRO STORICO - BRERA"); an
    # import given the prices alone leaves this empty rather than refusing.
    zone_description: Mapped[str] = mapped_column(String, default="")
    property_type_code: Mapped[str] = mapped_column(String, default="")
    property_type: Mapped[str] = mapped_column(String, default="")
    conservation_state: Mapped[str] = mapped_column(String, default="")
    # "sale" | "rent" — deliberately the vocabulary Property.contract already
    # uses, so a lookup can match a property without a translation table. One
    # source row carries both (Compr_* and Loc_*) and becomes up to two rows.
    contract: Mapped[str] = mapped_column(String, default="sale")
    min_sqm_price: Mapped[float] = mapped_column(Float)
    max_sqm_price: Mapped[float] = mapped_column(Float)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_omi_quotations_zone", OmiQuotation.municipality_code, OmiQuotation.zone_code)


class OmiZone(Base):
    """The perimeter of one OMI micro-zone: what turns a property's coordinates
    into the `zone_code` the quotations above are keyed by.

    Imported from the zone perimeters (KML) of the same Agenzia delle Entrate
    delivery, by `services/omi_zones.py`. Only the **national** supply carries
    them; a municipal one holds the prices and no geometry at all.

    `rings` is the geometry as JSON — a list of polygons, each `{"outer": [...],
    "holes": [...]}` with `[lat, lng]` vertices. A zone is genuinely several
    polygons (an exclave across a river) and genuinely has holes (a block that
    belongs to another zone), and both have to survive the round trip or the
    answer is wrong at exactly the addresses that are hardest to notice.

    The four `min_/max_` columns are the bounding box of those rings, stored so
    a lookup can discard almost every zone with an indexed comparison before any
    ray casting happens: a zone perimeter runs to hundreds of vertices, and the
    box is what keeps placing a property cheap enough to do in a loop.

    Keyed like `OmiQuotation` and for the same reason: `municipality_code` is the
    national comune code (`F205`), and a zone code is unique only *within* a
    comune — `B12` exists in most of Italy.
    """

    __tablename__ = "omi_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "YYYY/N", read from the KML's document title. Two semesters coexist and
    # the newest wins at lookup, exactly as the quotations do.
    semester: Mapped[str] = mapped_column(String, index=True)
    municipality_code: Mapped[str] = mapped_column(String, index=True)
    municipality: Mapped[str] = mapped_column(String, default="")
    zone_code: Mapped[str] = mapped_column(String, index=True)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    min_lng: Mapped[float] = mapped_column(Float)
    max_lng: Mapped[float] = mapped_column(Float)
    rings: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_omi_zones_zone", OmiZone.municipality_code, OmiZone.zone_code)
# The bounding-box pre-filter's own index. Latitude first because it is the
# narrower of the two over Italy's shape, so it discards more rows per probe.
Index("ix_omi_zones_bbox", OmiZone.min_lat, OmiZone.max_lat, OmiZone.min_lng, OmiZone.max_lng)


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    portal: Mapped[str] = mapped_column(String)  # immobiliare | idealista
    search_url: Mapped[str] = mapped_column(String)
    # EXTRA keywords for this profile, comma-separated: they ADD to global
    # settings keywords (UI displays them as "extra")
    excluded_keywords: Mapped[str] = mapped_column(Text, default="")
    # comma-separated channels ("telegram,email"); empty = all enabled channels
    notify_channels: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # ok | no_results | blocked | error — `ScrapeResult.outcome`, stored as it
    # came. `no_results` is a success: the portal answered, and its answer was
    # that nothing matches this search.
    last_run_status: Mapped[str] = mapped_column(String, default="")
    last_run_detail: Mapped[str] = mapped_column(String, default="")
    # How many scans in a row ended "blocked"/"error". A single failure is
    # noise (DataDome hands out 403s that clear within the hour); a streak
    # means the scraper is broken and the user must be told.
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    # True once the mandatory silent first scan has actually built a listing
    # baseline. Distinct from `last_run_at is None`: a scan attempt that gets
    # blocked/errored before fetching any listing still stamps `last_run_at`
    # (needed for scheduling), but must not consume the one-time notification
    # silence — otherwise the next attempt, which finally sees real listings,
    # fires a notification for every single one of them as if they were new.
    baseline_done: Mapped[bool] = mapped_column(Boolean, default=False)
    # True once the user has actually been alerted about the current outage:
    # keeps a portal blocked for a week from sending one message per scan.
    health_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # which listings this search has found (see ListingProfile). Deleting the
    # profile drops the links; whether the properties behind them go too is the
    # user's call at delete time (data_reset.delete_profile_results).
    listing_links: Mapped[list["ListingProfile"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
