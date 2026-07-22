"""The one place that reattaches UTC to a datetime read back from the DB.

SQLite has no timezone type: every aware datetime the ORM writes comes back
**naive**, while anything just built in memory (`datetime.now(UTC)`) is aware.
Comparing or sorting the two raises `TypeError: can't compare offset-naive and
offset-aware datetimes` — and `SessionLocal` uses `expire_on_commit=False`, so a
session that created a row keeps its aware value while every row it re-reads is
naive. Both kinds can therefore meet in one list.

This existed as five hand-rolled copies of the same two lines (scanner,
scheduler, availability_check, market_velocity, cookie_harvester). One of them
forgetting the reattachment is a 500 in whichever screen it feeds, so per the
"one fact, one implementation" convention it lives here now.
"""

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Naive input is assumed to be UTC (that is how it was written)."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def as_utc_or_none(value: datetime | None) -> datetime | None:
    """`as_utc` for nullable columns (`gone_at`, `sold_at`, `last_run_at`)."""
    return None if value is None else as_utc(value)
