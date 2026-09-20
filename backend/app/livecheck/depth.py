"""How deep one session gets before the portal stops answering it.

Every other mode in this package asks a portal *one* question per transport: can
you still be read at all. This one asks the question a scan's page budget
actually depends on — how many search pages a single session is allowed to walk
before the anti-bot decides it is not a person — and there is no way to look the
answer up. DataDome publishes that its rate limiting is a volume threshold each
customer configures for itself; nobody publishes Immobiliare's. So it is
measured, once, deliberately, and written down with the date it was true on.

The measurement imitates a scan rather than a diagnostic: one URL, the scraper's
own session (the saved cookie seeded, the rotated one kept exactly as a scan
keeps it), pages walked in order at `request_delay_seconds` plus the same
jitter, through the transport a scan of that portal really uses — api-next for
Immobiliare, HTML for Idealista. A reading taken any other way would be a
reading about the instrument.

**It stops at the first refusal and never asks again.** The refusal is the
result; a second request after it is the retry loop invariant 8 forbids, and
this address is the one the owner's scans leave from.
"""

from datetime import datetime
from pathlib import Path

from ..config import BASE_DIR, load_settings
from ..scrapers.base import BaseScraper
from ..scrapers.immobiliare import ImmobiliareScraper
from ..scrapers.parsing import detect_contract
from .budget import Budget
from .report import Attempt, Run, new_run_directory, redact, write_report
from .rungs import (
    OUTPUT_DIRNAME,
    Rung,
    Target,
    _capture_writer,
    _curl_rung,
    _scraper_for,
    immobiliare_api_target,
    immobiliare_params,
    portal_of,
    run_rungs,
    secrets_of,
)

# What the rung is called in the table. Not one of the transport names the other
# modes use, because it is not a transport being compared: it is the scanner's
# own session, and the row is about the page number rather than the way out.
RUNG_NAME = "scan session"


def depth_targets(
    scraper: BaseScraper,
    search_url: str,
    pages: int,
    budget: Budget,
    attempts: list[Attempt],
    *,
    search: str = "",
) -> list[Target]:
    """Pages 1..`pages` of one search, in the shape a scan would ask for them.

    Immobiliare is paged through api-next because that is what `scrape()` tries
    first and therefore what a scan spends its pages on; the geography lookup
    that builds those URLs is booked against the budget and recorded as its own
    row, exactly as the other modes record it. If it cannot be resolved the
    pages fall back to HTML, which is also a scan's fallback — a measurement
    that refused to run because a helper endpoint was down would be a worse
    answer than one taken through the transport the scan would have used next.
    """
    contract = detect_contract(search_url)
    params = None
    if isinstance(scraper, ImmobiliareScraper):
        params = immobiliare_params(scraper, search_url, budget, attempts, search=search)
    if params:
        return [
            immobiliare_api_target(params, search_url, page, contract)
            for page in range(1, pages + 1)
        ]
    # Page 1 is the URL as saved, not `next_page_url(url, 1)`: the first page a
    # scan fetches is the URL itself, and on Idealista the synthesised
    # `/lista-1.htm` is a different URL from the one the profile holds.
    urls = [search_url] + [
        scraper.next_page_url(search_url, page) or "" for page in range(2, pages + 1)
    ]
    return [
        Target(name=f"html p{page}", url=url, kind="html", contract=contract)
        for page, url in enumerate(urls, start=1)
        if url
    ]


def run_depth(
    search_url: str,
    pages: int,
    *,
    budget: Budget,
    out_root: Path | None = None,
    settings: dict | None = None,
    rung: Rung | None = None,
) -> Run:
    """Walk one search until the portal refuses, the pages run out, or the
    budget says no. Returns the same `Run` record every other mode writes.

    `rung` is injectable for the offline tests, which drive this loop — budget,
    pacing, parsers, report and all — with no socket anywhere.
    """
    settings = load_settings() if settings is None else settings
    secrets = secrets_of(settings)
    directory = new_run_directory(out_root or (BASE_DIR / OUTPUT_DIRNAME))
    portal = portal_of(search_url)
    run = Run(
        started_at=datetime.now().isoformat(timespec="seconds"),
        network="live",
        targets=[redact(search_url, secrets)],
        budget=budget.as_dict(),
        directory=str(directory),
        portal=portal,
    )
    if not portal:
        run.attempts.append(
            Attempt(
                portal="unknown",
                rung="-",
                target="-",
                url=redact(search_url, secrets),
                error="this URL belongs to no portal this tool can check",
            )
        )
        write_report(directory, run, secrets)
        return run

    scraper = _scraper_for(portal, budget.delay_seconds)
    targets = depth_targets(scraper, search_url, pages, budget, run.attempts, search="depth")
    run.attempts += run_rungs(
        portal,
        scraper,
        targets,
        [rung or _curl_rung(RUNG_NAME, scraper.session)],
        budget,
        capture=_capture_writer(directory),
        secrets=secrets,
        stop_on_refusal=True,
        search="depth",
    )
    run.credits_spent = budget.credits_spent
    write_report(directory, run, secrets)
    return run


def answered_pages(run: Run) -> int:
    """How many pages the portal actually served, which is the measurement.

    Answered, not parsed: the question is how much volume the anti-bot
    tolerated, so a page that came back empty, unreadable or with the origin's
    own 500 on it still counts, and only a refusal and a request never made do
    not. That is the same line `BaseScraper._fetch_once` draws for the passive
    count, and the two numbers have to mean the same thing to be comparable.
    The geography row is not a page and does not count.

    Counted off the attempts rather than tracked while looping, so a replayed
    report answers the same question as the live run that produced it.
    """
    pages = ("api-next", "html")
    return sum(
        1
        for a in run.attempts
        if a.kind in pages and a.status is not None and not a.blocked and not a.skipped
    )


def render_depth(run: Run) -> str:
    """The one sentence the run exists to produce, under the table.

    Three endings, and they are not interchangeable: refused (the measurement),
    stopped by the budget (a cap to raise, not a portal to investigate), or
    walked the whole way (no edge found *this far*, which is a bound and never a
    guarantee — invariant 26's habit applied to a number about ourselves).
    """
    answered = answered_pages(run)
    pace = f"one request every {run.budget.get('delay_seconds', 0)}s"
    refused = next((a for a in run.attempts if a.blocked), None)
    if refused is not None:
        status = f"HTTP {refused.status}" if refused.status else "a challenge"
        return f"refused at {refused.target} ({status}) after {answered} pages answered, at {pace}"
    if skipped := next((a for a in run.attempts if a.skipped), None):
        return f"stopped after {answered} pages by the run's own budget: {skipped.skipped}"
    return f"not refused in {answered} pages at {pace}: the edge is beyond this run, not absent"
