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
rung 4 runs: `scrape_api_mode="always"` (default) keeps today's behavior — a
configured key routes every fetch through the provider — while `"fallback"`
starts each scan on the free path and spends the paid rung only when the
profile's failure streak (the exact signal invariant 11 already counts) says
the free path is actually failing, descending again on recovery.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportDecision:
    """What the next scan should do about the managed scrape API."""

    start_on_api: bool  # first fetch goes straight through the provider
    allow_api_fallback: bool  # a fully-blocked local ladder may escalate to it
    label: str  # human-readable, for logs and the health panel


def _local_label(settings: dict) -> str:
    from .base import ProxyPool

    if ProxyPool.configured_proxies(settings):
        return "local (curl_cffi + proxy pool)"
    return "local (curl_cffi)"


def decide(consecutive_failures: int, settings: dict) -> TransportDecision:
    """Choose the transport for a profile's next scan.

    Pure and offline (like the scheduler's decision helpers) so it is fully
    unit-testable; `consecutive_failures` is the profile's invariant-11 streak.
    """
    key = (settings.get("scrape_api_key") or "").strip()
    if not key:
        return TransportDecision(False, False, _local_label(settings))
    mode = (settings.get("scrape_api_mode") or "always").strip().lower()
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
    key = (settings.get("scrape_api_key") or "").strip()
    if key and getattr(scraper, "use_scrape_api", True):
        return "managed scrape API"
    return _local_label(settings)
