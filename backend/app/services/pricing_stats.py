"""Local pricing statistics computed from listings already in SQLite.

Median €/sqm per (city, zone, contract), falling back to (city, contract)
when the zone has too few samples. No external data source and no AI:
the value is only as good as what the user's own profiles have collected,
which is why a minimum sample size is enforced — a "median" of two listings
would just be noise presented as insight.
"""
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Property

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
        entry, scope = None, None
        if zone and (city, zone, p.contract) in zone_medians:
            entry, scope = zone_medians[(city, zone, p.contract)], "zone"
        elif (city, p.contract) in city_medians:
            entry, scope = city_medians[(city, p.contract)], "city"
        if entry is None:
            continue
        med, _n = entry
        own = p.current_min_price / p.sqm
        p.area_median_sqm_price = round(med, 2)
        p.area_median_scope = scope
        p.sqm_price_delta_pct = round((own - med) / med * 100, 1)
