"""Persisted per-portal scraping health (plan B.5): the pipeline's degradation
made visible before scans "mysteriously stop finding listings".

Each completed profile scan accumulates into today's ScraperHealthSnapshot row
for its portal (attempts / successes / blocked / errors + the transport that
carried it). `get_health` serves the dashboard panel: block-rate trend per
portal plus the live per-profile streaks. Recording is fail-open like
pricing_stats.maybe_snapshot — observability must never take a scan down.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ScraperHealthSnapshot, SearchProfile

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30


def record_scan(db: Session, portal: str, status: str, transport: str) -> None:
    """Accumulate one profile-scan outcome into today's row for `portal`.

    Upsert-accumulate rather than once-per-day (PricingSnapshot's rule): a
    day's block RATE needs every scan counted, not the first one. Does not
    commit — the caller owns the transaction, exactly like the profile-health
    bookkeeping it rides along with.
    """
    try:
        today = datetime.now(UTC).date()
        row = db.scalar(
            select(ScraperHealthSnapshot).where(
                ScraperHealthSnapshot.captured_on == today,
                ScraperHealthSnapshot.portal == portal,
            )
        )
        if row is None:
            row = ScraperHealthSnapshot(captured_on=today, portal=portal)
            db.add(row)
        row.attempts = (row.attempts or 0) + 1
        if status == "blocked":
            row.blocked = (row.blocked or 0) + 1
        elif status == "error":
            row.errors = (row.errors or 0) + 1
        else:
            row.successes = (row.successes or 0) + 1
        row.last_transport = transport or row.last_transport
    except Exception:
        logger.exception("scraper health recording failed")


def get_health(db: Session, days: int = DEFAULT_WINDOW_DAYS) -> dict:
    """Health series per portal over the window + the live profile streaks."""
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    rows = db.scalars(
        select(ScraperHealthSnapshot)
        .where(ScraperHealthSnapshot.captured_on >= cutoff)
        .order_by(ScraperHealthSnapshot.captured_on, ScraperHealthSnapshot.id)
    ).all()
    portals: dict[str, dict] = {}
    for r in rows:
        entry = portals.setdefault(
            r.portal,
            {"portal": r.portal, "days": [], "last_transport": ""},
        )
        entry["days"].append(
            {
                "date": r.captured_on.isoformat(),
                "attempts": r.attempts or 0,
                "successes": r.successes or 0,
                "blocked": r.blocked or 0,
                "errors": r.errors or 0,
            }
        )
        entry["last_transport"] = r.last_transport or entry["last_transport"]

    for entry in portals.values():
        attempts = sum(d["attempts"] for d in entry["days"])
        failures = sum(d["blocked"] + d["errors"] for d in entry["days"])
        entry["attempts"] = attempts
        entry["failures"] = failures
        entry["block_rate"] = round(failures / attempts, 3) if attempts else 0.0

    streaks = [
        {
            "profile_id": p.id,
            "name": p.name,
            "portal": p.portal,
            "consecutive_failures": p.consecutive_failures or 0,
            "last_run_status": p.last_run_status or "",
        }
        for p in db.scalars(select(SearchProfile).where(SearchProfile.is_active.is_(True)))
    ]
    return {
        "window_days": days,
        "portals": sorted(portals.values(), key=lambda e: e["portal"]),
        "profiles": streaks,
    }
