"""The ladder itself: one rung per transport, one target per thing worth asking
for, and the loop that measures each pair on its own.

A *rung* is a way out of this machine — an impersonation, the saved cookie, a
browser, the paid provider's exit, the portal's own API. A *target* is a page
worth asking for: Immobiliare's api-next JSON (built by the scraper's own
`_api_params`, so geography resolves exactly as it does in a scan — invariant 7)
and its HTML search page, Idealista's HTML page and, where a key is configured,
its official API. Every (rung, target) pair is tried independently and reported
independently, because the whole point is that a scan collapses them into one
word and that word is usually wrong about which half failed.

**Nothing in `scrapers/` is changed to make this possible.** The scrapers are
driven from outside: their session builder, their parameter builder, their
parsers. A cookie-less rung is their own session with the jar emptied; the
browser rung is the harvester's launcher behind the `BrowserEngine` seam; the
paid rung is `transport.build_scrape_api_request`. Where this module reaches for
a private name it is because the public one would have run a whole scrape, and a
scrape is precisely what a diagnostic must not do.

`Rung.fetch` is an injected callable, so every test in `test_livecheck.py` drives
the real loop — budget, parsers, report and all — with no socket anywhere.
"""

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from curl_cffi import requests as curl_requests

from ..config import BASE_DIR, DB_PATH, load_settings
from ..scrapers import idealista_api
from ..scrapers.base import BaseScraper, RawListing
from ..scrapers.idealista import IdealistaScraper
from ..scrapers.immobiliare import API_LISTINGS, API_TOTAL_KEYS, ImmobiliareScraper
from ..scrapers.page_text import declared_result_total, has_block_marker, text_says_no_results
from ..scrapers.transport import (
    build_scrape_api_request,
    scrape_api_config,
    unwrap_scrape_api_response,
)
from .budget import CREDITS_PER_PAGE, Budget
from .report import (
    OK_OUTCOMES,
    Attempt,
    Run,
    capture_name,
    new_run_directory,
    read_report,
    redact,
    write_report,
)

# Where the captures go. Under the data directory but never *in* the database:
# this tool opens `case.db` read-only, for the saved search URLs, and nothing
# else. The directory is git-ignored — a capture is a portal's page, not ours.
OUTPUT_DIRNAME = "live-checks"

# The paid provider renders and solves a challenge before it answers, so its
# call is slow by design. The app's own 30 s ceiling is what turned a successful
# Scrapfly page into `curl: (28) Operation timed out` — billed, and thrown away
# unread. The instrument that has to see that page waits properly for it.
PAID_TIMEOUT_SECONDS = 180

# Long enough for a browser to get past a challenge, short enough that an
# unattended run cannot hang on one.
BROWSER_TIMEOUT_SECONDS = 45

PORTAL_HOSTS = {
    "immobiliare": "immobiliare.it",
    "idealista": "idealista.it",
}

# Every rung except the browser. Invariant 18: the browser is optional and
# opt-in, and naming it in `--rungs` is that opt-in — it is never in the default.
DEFAULT_EXCLUDED = ("browser",)


def portal_of(url: str) -> str:
    """Which portal a search URL belongs to, or "" for one this tool cannot check."""
    host = (urlparse(url).hostname or "").lower()
    for portal, domain in PORTAL_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return portal
    return ""


def active_profiles(db_path: Path | None = None) -> list[str]:
    """The search URLs of the enabled saved searches, read-only.

    Opened through a `mode=ro` URI rather than a plain path: a diagnostic that
    can take a write lock on the database the app is running against is one
    stray statement away from being the outage it was sent to investigate.
    """
    path = db_path or DB_PATH
    if not path.exists():
        return []
    uri = f"{path.as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        rows = conn.execute(
            "SELECT search_url FROM search_profiles WHERE is_active = 1 ORDER BY id"
        ).fetchall()
    return [row[0] for row in rows if row and row[0]]


# --- what a rung is -----------------------------------------------------


@dataclass
class Fetched:
    """What a rung's transport brought back, before anything is made of it."""

    status: int | None = None
    body: str = ""
    credits: int | None = None
    error: str = ""


@dataclass
class Target:
    """One page worth asking for."""

    name: str  # the TARGET column
    url: str
    kind: str  # api-next | html | official
    referer: str = ""
    # what the official-API parser needs and its payload does not carry
    contract: str = ""
    city: str = ""


@dataclass
class Rung:
    """One way out of this machine."""

    name: str
    fetch: Callable[[Target], Fetched]
    kinds: tuple[str, ...] = ("api-next", "html")
    # Direct rungs leave from this residential connection and answer to the
    # request cap, the spacing and the blocked streak. The paid one answers to
    # the credit cap and the account floor instead.
    direct: bool = True
    paid: bool = False
    remaining_credits: int | None = None
    cost: int = CREDITS_PER_PAGE
    # A rung that cannot run here at all (no cookie saved, no browser installed,
    # no API key): reported as skipped with this reason, never silently absent.
    unavailable: str = ""


class _BudgetExhausted(Exception):
    """Raised inside a metered session when the budget refuses the next request."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _MeteredSession:
    """A scraper session that books every request it makes against the budget.

    Wrapped rather than counted from outside because resolving geography is the
    scraper's own business — it may take one call or two, depending on whether
    the zone name resolves before the municipality does — and a number guessed
    here would be wrong exactly when the run is near its cap.
    """

    def __init__(self, inner: Any, portal: str, budget: Budget):
        self._inner = inner
        self._portal = portal
        self._budget = budget

    def get(self, *args, **kwargs):
        refusal = self._budget.refuse_direct(self._portal)
        if refusal:
            raise _BudgetExhausted(refusal)
        self._budget.wait(self._portal)
        self._budget.record_request(self._portal)
        return self._inner.get(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


# --- building the rungs -------------------------------------------------


def _session_for(scraper: BaseScraper, index: int, *, cookie: bool):
    """A fresh session on impersonation `index`, with or without the saved cookie.

    `BaseScraper._new_session` always sets the DataDome cookie when one is
    saved, so the cookie-less rungs empty the jar afterwards. That is the whole
    difference between `curl:<profile>` and `curl+cookie`, and measuring it is
    the only way to find out whether the cookie in settings is worth anything.
    """
    scraper._imp_index = index
    session = scraper._new_session()
    if not cookie:
        session.cookies.clear()
    return session


def _curl_rung(name: str, session: Any) -> Rung:
    def fetch(target: Target) -> Fetched:
        headers = {"Referer": target.referer} if target.referer else None
        resp = session.get(target.url, headers=headers)
        return Fetched(status=resp.status_code, body=resp.text)

    return Rung(name=name, fetch=fetch)


def _upstream_status(provider: str, resp: Any) -> int | None:
    """The status the *portal* gave the provider, which is the number that
    matters: the provider's own 200 only says the provider answered."""
    if provider != "scrapfly":
        return None
    try:
        status = resp.json()["result"]["status_code"]
    except Exception:
        return None
    return status if isinstance(status, int) else None


def _reported_cost(provider: str, resp: Any) -> int | None:
    """What the provider says this call billed. `None` when it did not say —
    never a zero, which the credit cap would read as a free call."""
    header = resp.headers.get("X-Scrapfly-Api-Cost") if provider == "scrapfly" else None
    if header and str(header).strip().isdigit():
        return int(str(header).strip())
    try:
        cost = resp.json()["context"]["cost"]["total"]
    except Exception:
        return None
    return cost if isinstance(cost, int) else None


def account_credits(provider: str, key: str, timeout: float = 20.0) -> tuple[int | None, str]:
    """(credits left on the provider account, why they could not be read).

    Scrapfly publishes it at `GET /account`
    (https://scrapfly.io/docs/account); the others do not, and unknown is
    refused by `Budget.refuse_paid` rather than assumed to be fine. The failure
    text is the exception's *type* only: its message would quote the URL back,
    and that URL carries the key.
    """
    if provider != "scrapfly":
        return None, f"{provider} publishes no account balance this tool can read"
    try:
        resp = curl_requests.get(
            "https://api.scrapfly.io/account", params={"key": key}, timeout=timeout
        )
        remaining = resp.json()["subscription"]["usage"]["scrape"]["remaining"]
    except Exception as e:
        return None, f"the account endpoint did not answer ({type(e).__name__})"
    if not isinstance(remaining, int):
        return None, "the account endpoint reported no remaining scrape credits"
    return remaining, ""


def _paid_rung(provider: str, key: str, remaining: int | None) -> Rung:
    session = curl_requests.Session(timeout=PAID_TIMEOUT_SECONDS)

    def fetch(target: Target) -> Fetched:
        req = build_scrape_api_request(provider, key, target.url)
        # Two providers, two shapes: Scrapfly takes the target in the query
        # string, Zyte posts it as JSON. Spelled out rather than passed through
        # `session.request` so the verb stays a literal the type checker can see.
        if req.method.upper() == "POST":
            resp = session.post(req.url, params=req.params, headers=req.headers, json=req.json_body)
        else:
            resp = session.get(req.url, params=req.params, headers=req.headers)
        credits = _reported_cost(provider, resp)
        if resp.status_code >= 400:
            return Fetched(
                status=resp.status_code,
                credits=credits,
                error=f"the provider refused (HTTP {resp.status_code}): {resp.text[:300]}",
            )
        try:
            body = unwrap_scrape_api_response(provider, resp)
        except Exception as e:
            return Fetched(
                status=resp.status_code, credits=credits, error=f"{type(e).__name__}: {e}"
            )
        return Fetched(
            status=_upstream_status(provider, resp) or resp.status_code,
            body=body,
            credits=credits,
        )

    return Rung(
        name=f"api:{provider}",
        fetch=fetch,
        direct=False,
        paid=True,
        remaining_credits=remaining,
    )


class _BrowserRung:
    """Playwright, opened once for the whole run and closed at the end.

    Invariant 18: optional, opt-in, and never a hard dependency. A machine
    without Playwright gets a skipped row saying so, which is a finding — "the
    browser rung was never tried here" is the answer to half the reports that
    start "the cookie grab does nothing".

    Always headless. This runs unattended under the cycle runner, where a window
    nobody is looking at is a run that hangs until its timeout.
    """

    def __init__(self):
        self._ctx: Any = None
        self._eng: Any = None
        self._pw: Any = None

    def _engine(self) -> Any:
        if self._eng is not None:
            return self._eng
        from ..scrapers.browser_engine import PlaywrightEngine
        from ..services import cookie_harvester

        def make_p():
            from playwright.sync_api import sync_playwright  # pyright: ignore[reportMissingImports]

            self._pw = sync_playwright().start()
            return self._pw

        self._ctx = cookie_harvester._launch(make_p, headless=True)
        page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._eng = PlaywrightEngine(self._ctx, page)
        return self._eng

    def fetch(self, target: Target) -> Fetched:
        eng = self._engine()
        status = eng.open(
            target.url,
            referer=target.referer or None,
            timeout_ms=BROWSER_TIMEOUT_SECONDS * 1000,
        )
        return Fetched(status=status, body=eng.content())

    def close(self) -> None:
        from ..services import cookie_harvester

        if self._ctx is not None:
            cookie_harvester._close_ctx(self._ctx)
            self._ctx = None
            self._eng = None
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:
                pass
            self._pw = None


def _official_rung() -> Rung:
    def fetch(target: Target) -> Fetched:
        payload = idealista_api.search(json.loads(target.url))
        return Fetched(status=200, body=json.dumps(payload, ensure_ascii=False))

    return Rung(name="official", fetch=fetch, kinds=("official",), direct=False)


def build_rungs(
    portal: str,
    scraper: BaseScraper,
    budget: Budget,
    *,
    settings: dict,
    browser: _BrowserRung | None = None,
) -> list[Rung]:
    """Every rung this machine could use against `portal`, in the order they are
    tried: free first, cheapest evidence first, money last."""
    rungs: list[Rung] = [
        _curl_rung(f"curl:{name}", _session_for(scraper, index, cookie=False))
        for index, name in enumerate(scraper.impersonations)
    ]

    cookie = (settings.get("datadome_cookie") or "").strip()
    cookie_rung = _curl_rung("curl+cookie", _session_for(scraper, 0, cookie=True))
    if not cookie:
        cookie_rung.unavailable = "no datadome_cookie is saved"
    rungs.append(cookie_rung)

    if browser is not None:
        rungs.append(Rung(name="browser", fetch=browser.fetch))
    else:
        from ..services import cookie_harvester

        reason = (
            ""
            if cookie_harvester.is_available()
            else "no browser is installed (the cookie harvester is not available)"
        )
        rungs.append(
            Rung(
                name="browser",
                fetch=lambda target: Fetched(error="the browser rung was not opened"),
                unavailable=reason or "the browser rung was not opened",
            )
        )

    provider, key = scrape_api_config()
    if provider and key:
        remaining, why = (
            account_credits(provider, key) if budget.paid else (None, "the paid rung needs --paid")
        )
        rung = _paid_rung(provider, key, remaining)
        if budget.paid and remaining is None and budget.credit_floor > 0:
            rung.unavailable = why
        rungs.append(rung)
    else:
        rungs.append(
            Rung(
                name="api:none",
                fetch=lambda target: Fetched(error="no provider configured"),
                direct=False,
                paid=True,
                unavailable="no scrape-API provider is configured in settings",
            )
        )

    if portal == "idealista":
        rung = _official_rung()
        if not idealista_api.is_configured():
            rung.unavailable = "no Idealista API key is configured"
        rungs.append(rung)

    return rungs


def select_rungs(rungs: list[Rung], wanted: list[str] | None) -> list[Rung]:
    """`--rungs` applied. A bare family name selects its whole family
    (`curl` takes every `curl:<profile>`, `api` takes the paid provider),
    an exact name selects just that one, and no filter means everything except
    the browser."""
    if not wanted:
        return [r for r in rungs if r.name not in DEFAULT_EXCLUDED]
    chosen = []
    for rung in rungs:
        family = rung.name.split(":", 1)[0]
        if rung.name in wanted or (":" in rung.name and family in wanted):
            chosen.append(rung)
    return chosen


# --- the targets --------------------------------------------------------


def _immobiliare_targets(
    scraper: ImmobiliareScraper,
    search_url: str,
    budget: Budget,
    attempts: list[Attempt],
    *,
    search: str = "",
) -> list[Target]:
    """The api-next page and the HTML page, in that order.

    Geography is resolved once for the run and then reused by every rung: the
    api-next URL it produces is a plain URL any transport can fetch, and
    resolving it per rung would be four identical lookups from an address this
    tool is trying not to annoy. The lookup is recorded as its own row — it is a
    request like any other, it can fail on its own, and invariant 7 means its
    failure is the reason api-next cannot be asked for at all.
    """
    html = Target(name="html p1", url=search_url, kind="html")
    attempt = Attempt(
        portal="immobiliare", rung="prepare", target="geography", kind="prepare", search=search
    )

    metered = _MeteredSession(scraper.session, "immobiliare", budget)
    original = scraper.session
    scraper.session = metered  # type: ignore[assignment]
    started = time.monotonic()
    try:
        params = scraper._api_params(search_url)
    except _BudgetExhausted as e:
        attempt.skipped = e.reason
        params = None
    except Exception as e:
        attempt.error = f"{type(e).__name__}: {e}"
        params = None
    finally:
        scraper.session = original
        attempt.elapsed_ms = int((time.monotonic() - started) * 1000)

    if params:
        attempt.resolved = True
        attempt.strategy = ",".join(sorted(params))
        budget.record_outcome("immobiliare", blocked=False)
        attempts.append(attempt)
        query = urlencode({**params, "pag": "1"}, doseq=True)
        api = Target(
            name="api-next p1",
            url=f"{API_LISTINGS}?{query}",
            kind="api-next",
            referer=search_url,
        )
        return [api, html]

    if not attempt.skipped and not attempt.error:
        attempt.error = "the geography lookup resolved nothing for this URL"
    if not attempt.skipped:
        # A geography endpoint that will not answer this address is a block
        # signal in its own right, and the streak has to feel it.
        attempt.refused_status = True
        budget.record_outcome("immobiliare", blocked=True)
    attempts.append(attempt)
    return [html]


def _idealista_targets(search_url: str) -> list[Target]:
    targets = [Target(name="html p1", url=search_url, kind="html")]
    plan = idealista_api.search_plan(search_url) if idealista_api.is_configured() else None
    if plan:
        params, city = plan
        targets.append(
            Target(
                name="official p1",
                # The official rung has no URL to fetch: its parameters travel as
                # a signed form post. They ride in `url` so one loop can drive
                # every rung, and they contain no credential of their own.
                url=json.dumps(params, sort_keys=True),
                kind="official",
                contract="rent" if params.get("operation") == "rent" else "sale",
                city=city,
            )
        )
    return targets


# --- the measured loop --------------------------------------------------


def _parse(
    scraper: BaseScraper, target: Target, body: str
) -> tuple[list[RawListing], str, int | None, bool]:
    """The body through the real parsers. Nothing is re-implemented here: a
    harness with its own parser measures its own parser."""
    if target.kind == "api-next":
        data = json.loads(body)
        results = data.get("results") or []
        listings = [
            listing
            for listing in (
                scraper._entry_to_listing(entry)  # type: ignore[attr-defined]
                for entry in results
                if isinstance(entry, dict)
            )
            if listing is not None
        ]
        declared = next(
            (data[key] for key in API_TOTAL_KEYS if isinstance(data.get(key), int)), None
        )
        # Invariant 26 in miniature: "nothing matched" is only ever the portal's
        # own count of zero, never an empty list on its own.
        return listings, "api-next", declared, (not results and declared == 0)
    if target.kind == "official":
        payload = json.loads(body)
        declared = payload.get("total") if isinstance(payload.get("total"), int) else None
        listings = idealista_api.to_listings(payload, target.contract, target.city)
        return (
            listings,
            "official-api",
            declared,
            (not payload.get("elementList") and declared == 0),
        )
    listings, strategy = scraper.parse_page(body, target.url)
    return listings, strategy, declared_result_total(body), text_says_no_results(body)


def _absorb(
    attempt: Attempt, fetched: Fetched, target: Target, scraper: BaseScraper, secrets: list[str]
) -> None:
    """Everything measurable about one answer, written onto the attempt."""
    attempt.status = fetched.status
    attempt.credits = fetched.credits
    attempt.error = redact(fetched.error, secrets)
    attempt.refused_status = fetched.status in (403, 429)
    body = fetched.body
    if not body:
        attempt.error = attempt.error or "the transport returned no body"
        return
    attempt.bytes = len(body.encode("utf-8", "replace"))
    attempt.block_marker = has_block_marker(body)
    attempt.captcha = "captcha" in body[:4000].lower()
    try:
        listings, strategy, declared, no_results = _parse(scraper, target, body)
    except Exception as e:
        attempt.error = attempt.error or f"the parser could not read it: {type(e).__name__}: {e}"
        return
    attempt.listings = len(listings)
    attempt.strategy = strategy
    attempt.declared_total = declared
    attempt.no_results = no_results
    attempt.samples = [{"title": listing.title, "price": listing.price} for listing in listings[:3]]


def run_rungs(
    portal: str,
    scraper: BaseScraper,
    targets: list[Target],
    rungs: list[Rung],
    budget: Budget,
    *,
    capture: Callable[[Attempt, Target, str], str] | None = None,
    secrets: list[str] | None = None,
    stop_at_first: bool = False,
    search: str = "",
) -> list[Attempt]:
    """Every rung against every target it serves, each measured on its own.

    The budget is consulted *before* each request and the refusal is recorded as
    the attempt, so a run that stopped early says so in the same table as the
    requests it did make. Nothing here retries: a rung that was refused is a
    finding, and asking again is the loop invariant 8 forbids.

    `stop_at_first` returns as soon as one attempt parses. It is what the
    reference suite runs on: the question there is "does this search still
    work", and once the cheapest rung has answered it, every further rung is a
    request that buys nothing and spends the address. The full matrix is still
    one flag away for the run that needs it.
    """
    secrets = secrets or []
    attempts: list[Attempt] = []
    for rung in rungs:
        for target in targets:
            if target.kind not in rung.kinds:
                continue
            attempt = Attempt(
                portal=portal,
                rung=rung.name,
                target=target.name,
                kind=target.kind,
                url=redact(target.url, secrets),
                contract=target.contract,
                city=target.city,
                search=search,
            )
            if rung.paid:
                refusal = rung.unavailable or budget.refuse_paid(rung.remaining_credits, rung.cost)
            elif rung.direct:
                refusal = rung.unavailable or budget.refuse_direct(portal)
            else:
                refusal = rung.unavailable
            if refusal:
                attempt.skipped = redact(refusal, secrets)
                attempts.append(attempt)
                continue

            if rung.direct:
                budget.wait(portal)
                budget.record_request(portal)
            started = time.monotonic()
            try:
                fetched = rung.fetch(target)
            except Exception as e:
                fetched = Fetched(error=f"{type(e).__name__}: {e}")
            attempt.elapsed_ms = int((time.monotonic() - started) * 1000)
            _absorb(attempt, fetched, target, scraper, secrets)

            if rung.paid:
                # Charged even when the call came back empty: a provider that
                # times out after solving the challenge still bills for it, which
                # is exactly how 7 failed scans cost 175 credits and left the cap
                # looking untouched.
                budget.spend(fetched.credits, rung.cost)
            if rung.direct:
                budget.record_outcome(portal, attempt.blocked)
            if capture is not None and fetched.body:
                attempt.capture = capture(attempt, target, fetched.body)
            attempts.append(attempt)
            if stop_at_first and attempt.outcome in OK_OUTCOMES:
                return attempts
    return attempts


# --- assembling a run ---------------------------------------------------


def _capture_writer(directory: Path) -> Callable[[Attempt, Target, str], str]:
    raw = directory / "raw"

    def write(attempt: Attempt, target: Target, body: str) -> str:
        raw.mkdir(parents=True, exist_ok=True)
        suffix = ".json" if target.kind in ("api-next", "official") else ".html"
        name = capture_name(attempt, suffix)
        (raw / name).write_text(body, encoding="utf-8", errors="replace")
        return f"raw/{name}"

    return write


def _secrets_of(settings: dict) -> list[str]:
    """Every value that must not appear anywhere in the output."""
    keys = ("scrape_api_key", "datadome_cookie", "idealista_api_key", "idealista_api_secret")
    return [str(settings.get(key) or "").strip() for key in keys if settings.get(key)]


def _scraper_for(portal: str, delay_seconds: float) -> BaseScraper:
    cls = ImmobiliareScraper if portal == "immobiliare" else IdealistaScraper
    return cls(delay_seconds=delay_seconds, max_pages=1)


def run_checks(
    urls: list[str],
    *,
    budget: Budget,
    rung_filter: list[str] | None = None,
    out_root: Path | None = None,
    settings: dict | None = None,
    labels: list[str] | None = None,
    stop_at_first: bool = False,
) -> Run:
    """Check every URL through every selected rung and write the record.

    One run, one directory: the table on stdout and `report.json` describe the
    same attempts, and the captures beside them are what `--replay` re-reads.

    `labels` names the searches, one per URL, and every attempt a URL produces
    carries its name — the geography row included, so a suite table can be read
    a search at a time. `stop_at_first` is passed through to each search's
    rungs.
    """
    settings = load_settings() if settings is None else settings
    secrets = _secrets_of(settings)
    directory = new_run_directory(out_root or (BASE_DIR / OUTPUT_DIRNAME))
    run = Run(
        started_at=datetime.now().isoformat(timespec="seconds"),
        network="live",
        targets=[redact(url, secrets) for url in urls],
        budget=budget.as_dict(),
        directory=str(directory),
    )
    capture = _capture_writer(directory)
    wants_browser = bool(rung_filter) and "browser" in (rung_filter or [])
    browser = _BrowserRung() if wants_browser else None

    names = list(labels or []) + [""] * max(0, len(urls) - len(labels or []))

    try:
        for url, name in zip(urls, names, strict=True):
            portal = portal_of(url)
            if not portal:
                run.attempts.append(
                    Attempt(
                        portal="unknown",
                        rung="-",
                        target="-",
                        url=redact(url, secrets),
                        error="this URL belongs to no portal this tool can check",
                        search=name,
                    )
                )
            elif refusal := budget.refuse_direct(portal):
                # Checked before the geography lookup rather than inside the
                # rungs, because that lookup succeeds against an endpoint
                # anti-bot rarely guards and clears the blocked streak as it
                # goes. Without this, a portal dropped on the first search of a
                # run would be resurrected by every search after it — the retry
                # loop invariant 8 forbids, spread over a list of URLs.
                run.attempts.append(
                    Attempt(
                        portal=portal,
                        rung="-",
                        target="-",
                        url=redact(url, secrets),
                        skipped=refusal,
                        search=name,
                    )
                )
            else:
                scraper = _scraper_for(portal, budget.delay_seconds)
                if isinstance(scraper, ImmobiliareScraper):
                    targets = _immobiliare_targets(scraper, url, budget, run.attempts, search=name)
                else:
                    targets = _idealista_targets(url)
                rungs = select_rungs(
                    build_rungs(portal, scraper, budget, settings=settings, browser=browser),
                    rung_filter,
                )
                run.attempts += run_rungs(
                    portal,
                    scraper,
                    targets,
                    rungs,
                    budget,
                    capture=capture,
                    secrets=secrets,
                    stop_at_first=stop_at_first,
                    search=name,
                )
    finally:
        if browser is not None:
            browser.close()

    run.credits_spent = budget.credits_spent
    write_report(directory, run, secrets)
    return run


def replay(directory: Path) -> Run:
    """Re-run the parsers over a saved run's captures, with no network at all.

    The transport numbers are the ones the original run measured — they are
    history and cannot be re-measured — while everything downstream of the body
    is computed again. That is the point: when a portal changes its page, this
    says so against captures already on disk instead of against the portal.
    """
    data = read_report(directory)
    run = Run(
        started_at=data.get("started_at", ""),
        network="replay",
        targets=list(data.get("targets") or []),
        budget=dict(data.get("budget") or {}),
        credits_spent=int(data.get("credits_spent") or 0),
        directory=str(directory),
    )
    fields = set(Attempt.__dataclass_fields__)
    scrapers: dict[str, BaseScraper] = {}
    for record in data.get("attempts") or []:
        attempt = Attempt(**{k: v for k, v in record.items() if k in fields})
        # Re-parsing is all this does; what the original run measured about the
        # transport stays as it was, and the counts below are recomputed.
        attempt.listings = 0
        attempt.strategy = ""
        attempt.declared_total = None
        attempt.no_results = False
        attempt.samples = []
        if not attempt.capture:
            attempt.skipped = attempt.skipped or "nothing was captured for this attempt"
            run.attempts.append(attempt)
            continue
        attempt.skipped = ""
        body = (directory / attempt.capture).read_text(encoding="utf-8", errors="replace")
        target = Target(
            name=attempt.target,
            url=attempt.url,
            kind=attempt.kind,
            contract=attempt.contract,
            city=attempt.city,
        )
        if attempt.portal not in scrapers:
            scrapers[attempt.portal] = _scraper_for(attempt.portal, 0.0)
        _absorb(
            attempt,
            Fetched(status=attempt.status, body=body, credits=attempt.credits),
            target,
            scrapers[attempt.portal],
            [],
        )
        run.attempts.append(attempt)
    return run
