"""Local pricing statistics computed from listings already in SQLite.

Median €/sqm per (city, zone, contract), falling back to (city, contract)
when the zone has too few samples. No external data source and no AI:
the value is only as good as what the user's own profiles have collected,
which is why a minimum sample size is enforced — a "median" of two listings
would just be noise presented as insight.
"""
import logging
import threading
from datetime import date
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PricingSnapshot, Property

logger = logging.getLogger(__name__)

# Serialises the "already captured today?" check against the insert. Without it,
# two callers that both finish a scan on a fresh day (or a scan and the daily
# scheduler job) each pass the check before either commits, and both write the
# full set of rows — the day then holds two snapshots per area, and the trend
# chart plots each twice. A single-process app, so a module lock is enough.
_snapshot_lock = threading.Lock()

# below this many comparable listings the median is not meaningful
MIN_SAMPLE = 3

ZoneKey = tuple[str, str, str]   # (city, zone, contract)
CityKey = tuple[str, str]        # (city, contract)


def compute_sqm_price_medians(
    db: Session,
) -> tuple[dict[ZoneKey, tuple[float, int]], dict[CityKey, tuple[float, int]]]:
    """Returns ({zone_key: (median, n)}, {city_key: (median, n)}).

    Uses active + filtered properties: "filtered" ones are still real market
    data points (a ground-floor flat has a valid price), while "gone" and
    "hidden" may carry stale prices.
    """
    rows = db.execute(
        select(
            Property.city, Property.zone, Property.contract,
            Property.current_min_price, Property.sqm,
        ).where(
            Property.status.in_(("active", "filtered")),
            Property.current_min_price.is_not(None),
            Property.sqm.is_not(None),
            Property.sqm > 0,
        )
    ).all()

    zone_samples: dict[ZoneKey, list[float]] = {}
    city_samples: dict[CityKey, list[float]] = {}
    for city, zone, contract, price, sqm in rows:
        city_norm = (city or "").strip().lower()
        if not city_norm:
            continue
        value = price / sqm
        city_samples.setdefault((city_norm, contract), []).append(value)
        zone_norm = (zone or "").strip().lower()
        if zone_norm:
            zone_samples.setdefault(
                (city_norm, zone_norm, contract), []
            ).append(value)

    zone_medians = {
        k: (median(v), len(v))
        for k, v in zone_samples.items() if len(v) >= MIN_SAMPLE
    }
    city_medians = {
        k: (median(v), len(v))
        for k, v in city_samples.items() if len(v) >= MIN_SAMPLE
    }
    return zone_medians, city_medians


def lookup_area_median(
    zone_medians: dict[ZoneKey, tuple[float, int]],
    city_medians: dict[CityKey, tuple[float, int]],
    city: str, zone: str, contract: str,
) -> tuple[tuple[float, int] | None, str | None]:
    """The zone median when available, falling back to the whole city.

    One implementation of the fallback rule, shared by the market-position
    annotation and market_velocity's agency deltas — two private copies of
    this had already started to look different. Expects normalized
    (lowercased, stripped) city/zone, like the median keys."""
    if zone:
        entry = zone_medians.get((city, zone, contract))
        if entry is not None:
            return entry, "zone"
    entry = city_medians.get((city, contract))
    return (entry, "city") if entry is not None else (None, None)


def annotate_market_position(db: Session, props: list[Property]) -> None:
    """Attaches transient attributes read by PropertyOut:

    - area_median_sqm_price: median €/sqm of the property's zone (or city);
    - area_median_scope: "zone" | "city" (what the median refers to);
    - sqm_price_delta_pct: how far this property is from that median
      (negative = cheaper than the area average).
    """
    if not props:
        return
    zone_medians, city_medians = compute_sqm_price_medians(db)
    for p in props:
        p.area_median_sqm_price = None
        p.area_median_scope = None
        p.sqm_price_delta_pct = None
        if not (p.current_min_price and p.sqm):
            continue
        city = (p.city or "").strip().lower()
        zone = (p.zone or "").strip().lower()
        entry, scope = lookup_area_median(
            zone_medians, city_medians, city, zone, p.contract
        )
        if entry is None:
            continue
        med, _n = entry
        own = p.current_min_price / p.sqm
        p.area_median_sqm_price = round(med, 2)
        p.area_median_scope = scope
        p.sqm_price_delta_pct = round((own - med) / med * 100, 1)


# --- Historical snapshots ----------------------------------------------------

def capture_snapshots(db: Session, today: date | None = None) -> int:
    """Persists today's median €/sqm for every area with enough comparables.

    At most one set of rows per day: the instantaneous median drifts as scans
    add listings through the day, and a single reading per day is all a trend
    line needs (the same once-per-day logic as backup.maybe_backup). Returns the
    number of rows written (0 if today is already captured or nothing qualifies).
    """
    today = today or date.today()
    # Hold the lock across the check AND the write: the whole point is that a
    # second caller cannot slip between "nothing for today yet" and the commit.
    with _snapshot_lock:
        already = db.scalar(
            select(PricingSnapshot.id).where(PricingSnapshot.captured_on == today)
        )
        if already is not None:
            return 0
        zone_medians, city_medians = compute_sqm_price_medians(db)
        rows = 0
        for (city, contract), (med, n) in city_medians.items():
            db.add(PricingSnapshot(captured_on=today, city=city, zone="",
                                   contract=contract, median_sqm_price=round(med, 2),
                                   sample_count=n))
            rows += 1
        for (city, zone, contract), (med, n) in zone_medians.items():
            db.add(PricingSnapshot(captured_on=today, city=city, zone=zone,
                                   contract=contract, median_sqm_price=round(med, 2),
                                   sample_count=n))
            rows += 1
        if rows:
            db.commit()
        return rows


def maybe_snapshot(db: Session) -> int:
    """Fail-open wrapper around capture_snapshots for the scan/scheduler paths:
    a snapshot is a nice-to-have, never worth taking a scan or startup down."""
    try:
        return capture_snapshots(db)
    except Exception:
        logger.exception("pricing snapshot failed")
        db.rollback()
        return 0


def get_trends(db: Session, city: str, zone: str, contract: str) -> dict:
    """Time series of median €/sqm for one area, oldest point first.

    City/zone are normalized to match how snapshots were stored. An empty zone
    asks for the whole-city aggregate (zone == "")."""
    city_norm = (city or "").strip().lower()
    zone_norm = (zone or "").strip().lower()
    rows = db.execute(
        select(PricingSnapshot.captured_on,
               PricingSnapshot.median_sqm_price,
               PricingSnapshot.sample_count)
        .where(PricingSnapshot.city == city_norm,
               PricingSnapshot.zone == zone_norm,
               PricingSnapshot.contract == contract)
        .order_by(PricingSnapshot.captured_on, PricingSnapshot.id)
    ).all()
    # Collapse to one point per day. New rows can no longer duplicate (see
    # `_snapshot_lock`), but databases written before that fix may hold two rows
    # for a day; two points at the same x drew the chart's line back on itself
    # and left stray dots. Keep the last row of each day (ordered by id).
    by_day: dict = {}
    for d, m, n in rows:
        by_day[d] = {"captured_on": d, "median_sqm_price": m, "sample_count": n}
    return {
        "city": city_norm, "zone": zone_norm, "contract": contract,
        "points": list(by_day.values()),
    }


def list_trend_areas(db: Session, contract: str) -> list[dict]:
    """Areas that have at least two snapshot points for the given contract —
    a single point is not yet a trend. Whole-city aggregates first, then zones,
    each ordered by how much history backs it."""
    rows = db.execute(
        select(PricingSnapshot.city, PricingSnapshot.zone,
               PricingSnapshot.contract, PricingSnapshot.captured_on)
        .where(PricingSnapshot.contract == contract)
    ).all()
    # Count DISTINCT days, not rows: a pre-fix duplicate would otherwise inflate
    # the "N days" label and could pass the >= 2 trend gate on a single day.
    days: dict[tuple[str, str, str], set] = {}
    for city, zone, ctr, day in rows:
        days.setdefault((city, zone, ctr), set()).add(day)
    areas = [
        {"city": city, "zone": zone, "contract": ctr, "point_count": len(ds)}
        for (city, zone, ctr), ds in days.items() if len(ds) >= 2
    ]
    # whole-city aggregates first, then most-observed
    areas.sort(key=lambda a: (a["zone"] != "", -a["point_count"], a["city"]))
    return areas
