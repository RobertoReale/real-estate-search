"""Persisted per-portal scraping health (plan B.5): the pipeline's degradation
made visible before scans "mysteriously stop finding listings".

Each completed profile scan accumulates into today's ScraperHealthSnapshot row
for its portal (attempts / successes / blocked / errors + the transport that
carried it, and what that transport billed). `get_health` serves the dashboard
panel: block-rate trend per portal, the live per-profile streaks, and the
month's spending against its ceiling. Recording is fail-open like
pricing_stats.maybe_snapshot — observability must never take a scan down.

The credit accounting is the same rows read a different way. Nothing else knows
what a month has cost: the provider bills per call, the app calls it from a
scheduler, and the receipts land here one scan at a time. So the month's total
is a sum over the days of the current calendar month, and it is the number the
transport policy is refused against.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ScraperHealthSnapshot, SearchProfile
from ..scrapers import transport_policy

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30


def record_scan(
    db: Session,
    portal: str,
    status: str,
    transport: str,
    credits: int = 0,
    credits_estimated: int = 0,
    api_calls: int = 0,
) -> None:
    """Accumulate one profile-scan outcome into today's row for `portal`.

    Upsert-accumulate rather than once-per-day (PricingSnapshot's rule): a
    day's block RATE needs every scan counted, not the first one. Does not
    commit — the caller owns the transaction, exactly like the profile-health
    bookkeeping it rides along with.

    `credits` is what the provider billed this scan in total; `credits_estimated`
    is the part of it charged at the measured page price because a receipt named
    no figure. The second is a subset of the first, never an addition to it.
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
            # `ok` and `no_results` alike: both mean the portal was reached and
            # said what it had. Counting a search over a quiet market as a
            # failure would put it on the same footing as a blocked one — in
            # the block rate here, and in the streak invariant 11 alerts on,
            # which would then never clear for a search that legitimately
            # matches nothing.
            row.successes = (row.successes or 0) + 1
        row.last_transport = transport or row.last_transport
        row.api_credits = (row.api_credits or 0) + max(0, credits)
        row.api_credits_estimated = (row.api_credits_estimated or 0) + max(0, credits_estimated)
        row.api_calls = (row.api_calls or 0) + max(0, api_calls)
    except Exception:
        logger.exception("scraper health recording failed")


def _month_start(today: date) -> date:
    return today.replace(day=1)


def credits_this_month(db: Session, today: date | None = None) -> dict:
    """What the paid transport has cost since the first of the month.

    A calendar month and not a rolling thirty days, because that is the unit the
    providers reset their free plans on: a rolling window would go on refusing
    for weeks after the allowance came back.
    """
    today = today or datetime.now(UTC).date()
    start = _month_start(today)
    rows = db.scalars(
        select(ScraperHealthSnapshot)
        .where(ScraperHealthSnapshot.captured_on >= start)
        .where(ScraperHealthSnapshot.captured_on <= today)
        .order_by(ScraperHealthSnapshot.captured_on, ScraperHealthSnapshot.id)
    ).all()
    spent = sum(r.api_credits or 0 for r in rows)
    estimated = sum(r.api_credits_estimated or 0 for r in rows)
    calls = sum(r.api_calls or 0 for r in rows)
    return {
        "month": start.isoformat()[:7],
        "spent": spent,
        "estimated": estimated,
        "calls": calls,
        "rows": rows,
    }


def _reached_on(rows, budget: int) -> str:
    """The first day of the month whose spending took the running total to the
    ceiling — the "since when" the notice has to be able to give. Empty while
    the ceiling stands untouched."""
    running = 0
    for row in rows:
        running += row.api_credits or 0
        if running >= budget:
            return row.captured_on.isoformat()
    return ""


def credit_budget(db: Session, settings: dict, today: date | None = None) -> dict:
    """The month's spending, its ceiling, and who is paying for the ceiling.

    `searches` names the active searches the pause is actually costing: the ones
    whose next scan would have gone through the provider if the credits were
    there. Working it out by asking the policy — with the budget taken out of
    the question — keeps one definition of "this search uses the paid rung"
    instead of a second copy of the mode/streak rules that could drift from it.
    """
    month = credits_this_month(db, today)
    budget = transport_policy.monthly_credit_budget(settings)
    spent = month["spent"]
    reached = transport_policy.budget_spent(spent, settings)
    affected: list[dict] = []
    if reached:
        for p in db.scalars(select(SearchProfile).where(SearchProfile.is_active.is_(True))):
            unconstrained = transport_policy.decide(p.consecutive_failures or 0, settings)
            if unconstrained.start_on_api or unconstrained.allow_api_fallback:
                affected.append({"profile_id": p.id, "name": p.name, "portal": p.portal})
    return {
        "month": month["month"],
        "monthly_credits": budget,
        "spent": spent,
        # A share of the spend the provider never quoted. The panel needs it to
        # know whether it may state the total flatly or must hedge it, which is
        # invariant 26's rule applied to money instead of to pages.
        "estimated": month["estimated"],
        "calls": month["calls"],
        "reached": reached,
        "reached_on": _reached_on(month["rows"], budget) if reached else "",
        "searches": affected,
    }


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
            {
                "portal": r.portal,
                "days": [],
                "last_transport": "",
                "api_credits": 0,
                "api_credits_estimated": 0,
                "api_calls": 0,
            },
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
        # Beside the transport label, because the label alone answers "what
        # carried this" and leaves "what did it cost" to a bill that arrives
        # somewhere else entirely.
        entry["api_credits"] += r.api_credits or 0
        entry["api_credits_estimated"] += r.api_credits_estimated or 0
        entry["api_calls"] += r.api_calls or 0

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
