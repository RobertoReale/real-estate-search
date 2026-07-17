"""ORM Models: Property (deduplicated real estate property), Listing (portal ad),
PriceHistory (price variations), SearchProfile (monitored search URL)."""
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    # ordered by id like price_history: the notifier and the exports read
    # listings[0].url as "the primary listing", which without order_by is
    # whatever the database happens to return
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="property", cascade="all, delete-orphan",
        order_by="Listing.id",
    )
    # ordered by id: the scanner reads price_history[-1] as the "latest
    # recorded change", and without order_by the order would not be guaranteed
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="property", cascade="all, delete-orphan",
        order_by="PriceHistory.id",
    )

    # Transient, request-scoped fields set by pricing_stats.annotate_market_position()
    # and match_score.annotate_match_scores(), read by PropertyOut: never
    # persisted, so plain attributes rather than mapped columns.
    area_median_sqm_price: float | None = None
    area_median_scope: str | None = None
    sqm_price_delta_pct: float | None = None
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
        back_populates="listing", cascade="all, delete-orphan",
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

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id"), primary_key=True, index=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    listing: Mapped[Listing] = relationship(back_populates="profile_links")
    profile: Mapped["SearchProfile"] = relationship(back_populates="listing_links")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), index=True)
    old_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_price: Mapped[float] = mapped_column(Float)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    property: Mapped[Property] = relationship(back_populates="price_history")


class ImportedListing(Base):
    """A listing found in the user's email inbox (IMAP import), waiting for
    review. Deliberately NOT a Listing: nothing enters the dashboard without
    the user accepting it, and the data quality is whatever the alert email
    contained (many of these listings are long gone from the portals).

    `status` lifecycle: pending -> accepted (a Property was created/merged,
    `property_id` set) or discarded. Discarded rows are kept: they are the
    memory that makes a re-scan of the same inbox idempotent.
    """
    __tablename__ = "imported_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    portal: Mapped[str] = mapped_column(String, index=True)
    portal_id: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str] = mapped_column(String, default="")
    zone: Mapped[str] = mapped_column(String, default="")
    rooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str] = mapped_column(String, default="")
    # guessed from the email text ("affitto"/"rent"), NOT authoritative like
    # a search URL: the user reviews it before accepting
    contract: Mapped[str] = mapped_column(String, default="sale")
    email_from: Mapped[str] = mapped_column(String, default="")
    email_subject: Mapped[str] = mapped_column(String, default="")
    email_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    property_id: Mapped[int | None] = mapped_column(
        ForeignKey("properties.id"), nullable=True
    )
    # Filled by an explicit availability check (AdProbe), never by the scan:
    # NULL means "never checked", which is not the same as "gone". The check
    # itself answers None when the portal blocks it, so the column keeps its
    # previous value rather than condemning a listing on no evidence.
    is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
    last_run_status: Mapped[str] = mapped_column(String, default="")  # ok | blocked | error
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
        back_populates="profile", cascade="all, delete-orphan",
    )
