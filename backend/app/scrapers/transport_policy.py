"""Health-driven, cost-aware choice of the scraping transport (plan B.3).

The project already ships every transport the 2026 anti-bot landscape calls
for — TLS rotation (invariant 8), a proxy pool (base.ProxyPool), reactive
cookie recovery and browsers (invariants 16/18), and a managed scrape API.
What was missing is the *policy*: which one should the NEXT fetch start on?

This module is that policy, and nothing else: pure decisions, no network, no
new bypass code — the rungs' implementations live where they always did, and
invariants 8/16/18 are untouched. The ladder, cheapest first:

    0  curl_cffi + TLS rotation + user cookie          (free)
    1  + residential proxy from the pool               (¢, when configured)
    2  fresh DataDome cookie via headless browser      (reactive, opt-in)
    3  persistent browser session                      (reactive, opt-in)
    4  managed scrape API                              (€ per call, needs key)

Rungs 2–3 stay reactive inside the existing flows; the decision here is when
rung 4 runs: `scrape_api_mode="fallback"` (default) starts each scan on the
free path and spends the paid rung only when the profile's failure streak (the
exact signal invariant 11 already counts) says the free path is actually
failing, descending again on recovery; `"always"` routes every fetch through
the provider unconditionally.

Above both of them sits the money. Rung 4 is metered and the scans are on a
timer, which is a combination that spends a free plan without anybody deciding
to: `scrape_api_monthly_credits` is the ceiling per calendar month, summed from
what the provider's own receipts said (`services/scraper_health.py`), and
reaching it takes rung 4 off the ladder entirely — not just as a starting point
but as the escalation a blocked local ladder falls back on, which is the half
that would otherwise keep paying. The app then scans on the free path and says
what it stopped doing, because a search that silently changed transport is a
search whose results silently changed too.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportDecision:
    """What the next scan should do about the managed scrape API."""

    start_on_api: bool  # first fetch goes straight through the provider
    allow_api_fallback: bool  # a fully-blocked local ladder may escalate to it
    label: str  # human-readable, for logs and the health panel


def _local_label(settings: dict) -> str:
    from .transport import ProxyPool

    if ProxyPool.configured_proxies(settings):
        return "local (curl_cffi + proxy pool)"
    return "local (curl_cffi)"


def monthly_credit_budget(settings: dict) -> int:
    """The month's ceiling in provider credits; 0 (or a negative, or nonsense)
    means no ceiling of ours and the provider's own quota is the only limit."""
    try:
        budget = int(settings.get("scrape_api_monthly_credits") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, budget)


def budget_spent(credits_spent: int, settings: dict) -> bool:
    """Has this calendar month's paid allowance been used up?"""
    budget = monthly_credit_budget(settings)
    return budget > 0 and credits_spent >= budget


def decide(consecutive_failures: int, settings: dict, credits_spent: int = 0) -> TransportDecision:
    """Choose the transport for a profile's next scan.

    Pure and offline (like the scheduler's decision helpers) so it is fully
    unit-testable; `consecutive_failures` is the profile's invariant-11 streak
    and `credits_spent` is what the provider has already billed this calendar
    month (`services/scraper_health.credits_this_month`). Called with the
    default `credits_spent=0` it answers the question without the budget in it,
    which is how the health panel works out *which* searches the ceiling is
    currently costing something.
    """
    key = (settings.get("scrape_api_key") or "").strip()
    if not key:
        return TransportDecision(False, False, _local_label(settings))
    if budget_spent(credits_spent, settings):
        # Both flags off, deliberately. Leaving the fallback on would keep every
        # blocked scan paying — and a blocked scan is precisely when the ladder
        # reaches for rung 4, so the ceiling would hold only while it was not
        # being tested.
        return TransportDecision(
            False,
            False,
            f"{_local_label(settings)} — scrape API paused, "
            f"{credits_spent} of {monthly_credit_budget(settings)} monthly credits spent",
        )
    mode = (settings.get("scrape_api_mode") or "fallback").strip().lower()
    if mode != "fallback":
        return TransportDecision(True, True, "managed scrape API")
    threshold = int(settings.get("transport_escalate_after_failures") or 2)
    if threshold > 0 and consecutive_failures >= threshold:
        return TransportDecision(
            True,
            True,
            f"managed scrape API (escalated: {consecutive_failures} consecutive failures)",
        )
    return TransportDecision(False, True, f"{_local_label(settings)}, scrape API on block")


def transport_used(scraper, settings: dict) -> str:
    """Label of the transport a scraper actually ended up on, for the health
    snapshot ("started local, finished on the API" must be visible)."""
    # Checked first because it is the one path that met no anti-bot at all: a
    # scan Idealista answered itself never touched curl_cffi, a proxy or a
    # provider, and labelling it "local" would credit the block-rate trend to a
    # transport that did no work (scrapers/idealista_api.py).
    if getattr(scraper, "used_official_api", False):
        return "idealista official API"
    key = (settings.get("scrape_api_key") or "").strip()
    if key and getattr(scraper, "use_scrape_api", True):
        return "managed scrape API"
    return _local_label(settings)
