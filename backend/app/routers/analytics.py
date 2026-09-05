"""Read-only market analysis over the local scan history: days-on-market and
agency behaviour, plus the €/sqm trend charts and the listings behind a median.

Everything here is computed from what this installation has already collected,
so the numbers only start meaning something after the app has been running for
a few weeks — a limitation each endpoint's docstring repeats, because unstated
it reads as a bug.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services.market_velocity import compute_market_velocity
from ..services.pricing_stats import area_comparables, get_trends, list_trend_areas
from .selection import annotate

router = APIRouter()


@router.get("/api/market-velocity", response_model=schemas.MarketVelocityOut)
def market_velocity(
    db: Session = Depends(get_db),
    contract: str = Query("sale", pattern="^(sale|rent)$"),
    city: str | None = None,
):
    """Days-on-market and sell-through per neighborhood, plus agency pricing
    behavior. Values are computed from local scan history only, so they are
    meaningful once the database has been accumulating for a few weeks."""
    return compute_market_velocity(db, contract=contract, city=city)


@router.get("/api/pricing-trends/areas", response_model=list[schemas.TrendAreaOut])
def pricing_trend_areas(
    db: Session = Depends(get_db),
    contract: str = Query("sale", pattern="^(sale|rent)$"),
):
    """Areas with at least two daily snapshots — the ones worth charting."""
    return list_trend_areas(db, contract)


@router.get("/api/pricing-trends", response_model=schemas.PricingTrendOut)
def pricing_trends(
    db: Session = Depends(get_db),
    city: str = Query(..., min_length=1),
    zone: str = "",
    contract: str = Query("sale", pattern="^(sale|rent)$"),
):
    """Median €/sqm over time for one area (empty zone = whole city). The series
    is built from daily snapshots (pricing_snapshots), so it only starts saying
    something after the app has run for several days."""
    return get_trends(db, city=city, zone=zone, contract=contract)


@router.get("/api/pricing-trends/comparables", response_model=list[schemas.PropertyOut])
def pricing_trend_comparables(
    db: Session = Depends(get_db),
    city: str = Query(..., min_length=1),
    zone: str = "",
    contract: str = Query("sale", pattern="^(sale|rent)$"),
):
    """The listings behind an area's *current* median €/sqm — the concrete data
    the chart's latest point summarises. Snapshots keep only the median and the
    count, so this is necessarily the set as it stands today, not a past point's
    (see pricing_stats.area_comparables). Same properties, annotated exactly like
    the grid, so the same property detail opens from the chart."""
    props = area_comparables(db, city=city, zone=zone, contract=contract)
    annotate(db, props)
    return props
