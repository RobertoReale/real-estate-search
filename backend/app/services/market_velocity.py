"""Market velocity signals: how fast listings leave the market, and how each
agency prices and re-prices what it lists.

Two things this module measures, both derived from data the scans already
collect (`first_seen_at`, the `gone` status with its `gone_at` timestamp,
`first_price` vs `current_min_price`, `Listing.agency`):

- **Area velocity** — median days-on-market and sell-through rate per
  neighborhood, so a zone where flats vanish in three weeks reads
  differently from one where they sit for six months.
- **Agency behavior** — which agencies systematically list above the local
  median €/sqm, and which ones discount the most afterwards. An agency that
  does both is asking for an anchor price it does not expect to get.

Three honest limitations, deliberately surfaced in the API payload rather
than hidden behind a confident number:

1. `first_seen_at` is when *this installation* first saw the listing, not
   when the portal published it. Every property already online when the user
   created the profile has its age truncated, so early days-on-market values
   are underestimates. They converge as the database ages.
2. "gone" means "no scan has seen it for GONE_AFTER_DAYS days" — sold,
   rented, withdrawn, or simply re-published under a new portal id. It is
   market exit, not proof of a sale. A property the user explicitly marks
   "sold" *is* a confirmed close (with a real `sold_at` date), and both
   count towards the closed set — the `sold` counts break out how many of
   the closes are confirmed rather than inferred.
3. Medians below MIN_SAMPLE observations are not returned at all. The same
   rule as pricing_stats.py, for the same reason: a median of two listings
   is noise wearing the costume of a statistic.
"""
from datetime import datetime, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Property
from .pricing_stats import compute_sqm_price_medians, lookup_area_median

# below this many observations a median is not reported (see module docstring)
MIN_SAMPLE = 3


def _as_utc(value: datetime) -> datetime:
    """SQLite hands back naive datetimes; they were all written in UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _is_closed(prop: Property) -> bool:
    """Left the market: inferred exit ("gone") or user-confirmed sale ("sold")."""
    return prop.status in ("gone", "sold")


def _days_on_market(prop: Property, now: datetime) -> float:
    """Days between the first sighting and the exit from the market (or now,
    for properties still listed)."""
    if prop.sold_at is not None:
        # user-confirmed sale: a real, precise close date
        end = _as_utc(prop.sold_at)
    elif prop.gone_at is not None:
        end = _as_utc(prop.gone_at)
    elif _is_closed(prop):
        # marked closed before its timestamp existed: last_seen_at is the best proxy
        end = _as_utc(prop.last_seen_at)
    else:
        end = now
    return max((end - _as_utc(prop.first_seen_at)).total_seconds() / 86400.0, 0.0)


def _drop_pct(prop: Property) -> float | None:
    """Discount from the first price ever seen, as a positive percentage.
    None when the price never dropped."""
    if not (prop.first_price and prop.current_min_price):
        return None
    if prop.current_min_price >= prop.first_price:
        return None
    return (prop.first_price - prop.current_min_price) / prop.first_price * 100.0


def _median_or_none(values: list[float]) -> float | None:
    return round(median(values), 1) if len(values) >= MIN_SAMPLE else None


def _area_row(city: str, zone: str, scope: str, props: list[Property],
              now: datetime) -> dict:
    closed = [p for p in props if _is_closed(p)]
    sold = [p for p in props if p.status == "sold"]
    live = [p for p in props if not _is_closed(p)]
    dropped = [p for p in props if _drop_pct(p) is not None]
    return {
        "city": city,
        "zone": zone,
        "scope": scope,
        "sample": len(props),
        # closed = left the market (inferred "gone" + confirmed "sold")
        "closed": len(closed),
        # of which the user has confirmed as an actual sale
        "sold": len(sold),
        # only closed listings have a *complete* days-on-market window
        "median_days_to_gone": _median_or_none([_days_on_market(p, now) for p in closed]),
        # the subset above with a confirmed sale date — the strongest signal
        "median_days_to_sold": _median_or_none([_days_on_market(p, now) for p in sold]),
        # how long what is still online has been sitting there
        "median_days_listed": _median_or_none([_days_on_market(p, now) for p in live]),
        "sell_through_pct": round(len(closed) / len(props) * 100.0, 1),
        "price_drop_pct": round(len(dropped) / len(props) * 100.0, 1),
    }


def compute_area_velocity(
    props: list[Property], now: datetime
) -> list[dict]:
    """One row per neighborhood (and one per city, aggregating its zones),
    sorted fastest-moving first."""
    by_zone: dict[tuple[str, str], list[Property]] = {}
    by_city: dict[str, list[Property]] = {}
    for p in props:
        city = (p.city or "").strip()
        if not city:
            continue
        by_city.setdefault(city, []).append(p)
        zone = (p.zone or "").strip()
        if zone:
            by_zone.setdefault((city, zone), []).append(p)

    rows = [
        _area_row(city, zone, "zone", group, now)
        for (city, zone), group in by_zone.items()
        if len(group) >= MIN_SAMPLE
    ]
    rows += [
        _area_row(city, "", "city", group, now)
        for city, group in by_city.items()
        if len(group) >= MIN_SAMPLE
    ]
    # areas whose median cannot be computed yet still carry a sell-through
    # rate worth showing, so they are sorted last instead of dropped
    rows.sort(key=lambda r: (r["median_days_to_gone"] is None,
                             r["median_days_to_gone"] or 0.0))
    return rows


def compute_agency_behavior(
    db: Session, props: list[Property], now: datetime
) -> list[dict]:
    """One row per agency: how it prices against the local median €/sqm, and
    how much it discounts afterwards."""
    zone_medians, city_medians = compute_sqm_price_medians(db)

    def sqm_delta_pct(p: Property) -> float | None:
        """How far this property's €/sqm sits from its area median."""
        if not (p.current_min_price and p.sqm):
            return None
        city = (p.city or "").strip().lower()
        zone = (p.zone or "").strip().lower()
        entry, _scope = lookup_area_median(
            zone_medians, city_medians, city, zone, p.contract
        )
        if entry is None:
            return None
        med, _n = entry
        return ((p.current_min_price / p.sqm) - med) / med * 100.0

    # a Property merged across portals can carry several agencies; each one
    # published it, so each one answers for its price — but only once.
    # Keyed casefolded (like city/zone normalization elsewhere): the same
    # agency scraped with different casing across portals would otherwise
    # split its sample below MIN_SAMPLE and vanish from the table.
    by_agency: dict[str, dict[int, Property]] = {}
    display_name: dict[str, str] = {}
    for p in props:
        for listing in p.listings:
            agency = (listing.agency or "").strip()
            if agency:
                key = agency.casefold()
                display_name.setdefault(key, agency)
                by_agency.setdefault(key, {})[p.id] = p

    rows = []
    for agency_key, props_by_id in by_agency.items():
        group = list(props_by_id.values())
        if len(group) < MIN_SAMPLE:
            continue
        drops = [d for d in (_drop_pct(p) for p in group) if d is not None]
        deltas = [d for d in (sqm_delta_pct(p) for p in group) if d is not None]
        gone = [p for p in group if _is_closed(p)]
        rows.append({
            "agency": display_name[agency_key],
            "sample": len(group),
            "price_drop_pct": round(len(drops) / len(group) * 100.0, 1),
            # median discount among the listings that *did* drop: mixing in
            # the unchanged ones would report a discount nobody ever offered
            "median_drop_pct": _median_or_none(drops),
            # positive = lists above the neighborhood median €/sqm
            "median_sqm_price_delta_pct": _median_or_none(deltas),
            "priced_sample": len(deltas),
            "median_days_to_gone": _median_or_none(
                [_days_on_market(p, now) for p in gone]
            ),
        })
    rows.sort(key=lambda r: r["sample"], reverse=True)
    return rows


def compute_market_velocity(
    db: Session, contract: str = "sale", city: str | None = None
) -> dict:
    """Full payload for GET /api/market-velocity.

    Excludes "hidden" properties (the user removed them from their market on
    purpose) but keeps "filtered" ones: a ground-floor flat excluded by a
    keyword is still a real listing that took real days to sell. "sold" ones
    are kept and counted as confirmed closes (that is the whole point of the
    state).
    """
    now = datetime.now(timezone.utc)
    query = (
        select(Property)
        .options(selectinload(Property.listings))
        .where(
            Property.contract == contract,
            # "sold" joins the closed set here: it is a confirmed market exit,
            # the very datapoint this module's docstring notes "gone" lacks.
            Property.status.in_(("active", "filtered", "gone", "sold")),
        )
    )
    if city:
        query = query.where(Property.city.ilike(f"%{city}%"))
    props = list(db.scalars(query))

    oldest = min((_as_utc(p.first_seen_at) for p in props), default=None)
    return {
        "contract": contract,
        "city": city or "",
        "generated_at": now,
        "min_sample": MIN_SAMPLE,
        "total_properties": len(props),
        "closed_properties": sum(1 for p in props if _is_closed(p)),
        # of the closed ones, how many the user confirmed as a real sale
        "sold_properties": sum(1 for p in props if p.status == "sold"),
        # how far back the observation window reaches: days-on-market values
        # cannot be older than this, and the UI says so
        "tracking_since": oldest,
        "areas": compute_area_velocity(props, now),
        "agencies": compute_agency_behavior(db, props, now),
    }
