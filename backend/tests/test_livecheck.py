"""The live-check harness, offline.

Every test here drives the real loop — the real budget, the real parsers, the
real report writer — with the transport replaced by a callable. That is what
`Rung.fetch` is for: a harness that had to reach a portal to test itself would be
untestable exactly where it matters, because the behaviour worth pinning down is
what it does when a portal *refuses*.

Three things are pinned harder than the rest, because getting them wrong costs
something real: the request cap and the blocked streak (a run that keeps asking
is how this address gets blocked for a day — invariant 8), the credit cap and the
account floor (the paid rung spends money, and a call that timed out is billed
all the same), and the redaction (the provider key travels in a query string, so
it is one careless line away from being committed).

The page fixtures are synthetic. This repository is public, and a portal's own
markup is not ours to publish.
"""

import json
import socket
import sqlite3
from pathlib import Path

import pytest

from app.livecheck.budget import BLOCKED_STREAK_LIMIT, CREDITS_PER_PAGE, Budget
from app.livecheck.report import (
    Attempt,
    Run,
    new_run_directory,
    redact,
    render,
    render_table,
    succeeded,
    verdicts,
    write_report,
)
from app.livecheck.rungs import (
    Fetched,
    Rung,
    Target,
    _BudgetExhausted,
    _capture_writer,
    _immobiliare_targets,
    _MeteredSession,
    active_profiles,
    build_rungs,
    portal_of,
    replay,
    run_checks,
    run_rungs,
    select_rungs,
)
from app.scrapers.idealista import IdealistaScraper
from app.scrapers.immobiliare import ImmobiliareScraper

SEARCH_URL = "https://www.immobiliare.it/vendita-case/milano/bicocca/"
FAKE_KEY = "sf_live_0123456789abcdef0123456789abcdef"

API_NEXT = json.dumps(
    {
        "count": 812,
        "results": [
            {
                "realEstate": {
                    "id": 777,
                    "title": "Bilocale zona Bicocca",
                    "price": {"value": 199000},
                    "properties": [
                        {
                            "surface": "60 m²",
                            "rooms": "2",
                            "location": {"city": "Milano", "macrozone": "Bicocca"},
                        }
                    ],
                },
                "seo": {"url": "https://www.immobiliare.it/annunci/777/"},
            },
            {
                "realEstate": {
                    "id": 778,
                    "title": "Trilocale via Chiese",
                    "price": {"value": 289000},
                    "properties": [
                        {
                            "surface": "85 m²",
                            "rooms": "3",
                            "location": {"city": "Milano", "macrozone": "Bicocca"},
                        }
                    ],
                },
                "seo": {"url": "https://www.immobiliare.it/annunci/778/"},
            },
        ],
    }
)

PAGE_HTML = """
<html><head>
<script type="application/ld+json">
{"@type": "ItemList", "itemListElement": [
  {"item": {"@type": "RealEstateListing",
            "url": "https://www.immobiliare.it/annunci/999/",
            "name": "Quadrilocale viale Sarca",
            "offers": {"price": "410000"},
            "numberOfRooms": 4,
            "floorSize": {"value": "120"},
            "address": {"addressLocality": "Milano"}}}
]}
</script></head><body></body></html>
"""

BLOCKED_HTML = "<html><body>Please enable JS and disable any ad blocker to continue</body></html>"


# --- helpers ------------------------------------------------------------


def a_budget(**kwargs) -> Budget:
    """A budget that never really sleeps, so a whole run takes microseconds."""
    kwargs.setdefault("delay_seconds", 0.0)
    kwargs.setdefault("sleep", lambda _seconds: None)
    return Budget(**kwargs)


def a_rung(name: str, answers: list[Fetched], **kwargs) -> Rung:
    """A rung whose transport is a list of canned answers, one per call."""
    queue = list(answers)

    def fetch(_target: Target) -> Fetched:
        return queue.pop(0) if queue else Fetched(error="the fake ran out of answers")

    return Rung(name=name, fetch=fetch, **kwargs)


def named_rungs(*names: str) -> list[Rung]:
    return [Rung(name=name, fetch=lambda _target: Fetched()) for name in names]


def html_target() -> Target:
    return Target(name="html p1", url=SEARCH_URL, kind="html")


def api_target() -> Target:
    return Target(
        name="api-next p1",
        url="https://www.immobiliare.it/api-next/search-list/listings/?idComune=8042&pag=1",
        kind="api-next",
    )


class FakeResponse:
    def __init__(self, payload, status: int = 200):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeGeoSession:
    """Stands in for the scraper's session while geography resolves."""

    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self._status = status
        self.calls = 0

    def get(self, _url, **_kwargs):
        self.calls += 1
        return FakeResponse(self._payload, self._status)


MILANO_GEO = [{"type": 2, "id": "8042", "parents": [{"type": 1, "id": "MI"}]}]


@pytest.fixture
def scraper():
    return ImmobiliareScraper()


# --- the residential connection -----------------------------------------


def test_the_request_cap_stops_the_run(scraper):
    budget = a_budget(max_requests=2)
    rungs = [a_rung(f"curl:p{i}", [Fetched(status=200, body=PAGE_HTML)]) for i in range(4)]

    attempts = []
    for rung in rungs:
        attempts += run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert [a.outcome for a in attempts] == ["ok", "ok", "skipped", "skipped"]
    assert attempts[2].skipped == "request cap reached (2 per run)"
    assert budget.requests_made("immobiliare") == 2


def test_three_blocks_in_a_row_drop_the_portal(scraper):
    budget = a_budget()
    rungs = [a_rung(f"curl:p{i}", [Fetched(status=403)]) for i in range(BLOCKED_STREAK_LIMIT + 1)]

    attempts = []
    for rung in rungs:
        attempts += run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert [a.outcome for a in attempts[:-1]] == ["blocked"] * BLOCKED_STREAK_LIMIT
    assert attempts[-1].outcome == "skipped"
    assert "blocked attempts in a row" in attempts[-1].skipped
    # The streak ended the run, not the cap: the cap was nowhere near.
    assert budget.requests_made("immobiliare") == BLOCKED_STREAK_LIMIT


def test_a_rung_that_got_through_clears_the_streak(scraper):
    budget = a_budget()
    answers = [
        Fetched(status=403),
        Fetched(status=403),
        Fetched(status=200, body=PAGE_HTML),
        Fetched(status=403),
    ]

    attempts = []
    for index, answer in enumerate(answers):
        attempts += run_rungs(
            "immobiliare", scraper, [html_target()], [a_rung(f"curl:p{index}", [answer])], budget
        )

    assert [a.outcome for a in attempts] == ["blocked", "blocked", "ok", "blocked"]
    assert budget.blocked_streak("immobiliare") == 1


def test_a_wall_served_with_a_200_still_counts_as_a_block(scraper):
    budget = a_budget()
    rung = a_rung("curl:safari184", [Fetched(status=200, body=BLOCKED_HTML)])

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert attempt.status == 200
    assert attempt.block_marker
    assert attempt.outcome == "blocked"
    assert budget.blocked_streak("immobiliare") == 1


def test_requests_to_one_portal_are_spaced_out(scraper):
    slept: list[float] = []
    budget = Budget(delay_seconds=6.0, sleep=slept.append, now=lambda: 0.0)
    rung = a_rung("curl:safari184", [Fetched(status=200, body=PAGE_HTML)] * 2)

    run_rungs("immobiliare", scraper, [api_target(), html_target()], [rung], budget)

    # One wait, before the second request; the jitter only ever adds to the delay.
    assert len(slept) == 1
    assert slept[0] >= 6.0


def test_the_metered_session_refuses_past_the_cap():
    budget = a_budget(max_requests=1)

    class Inner:
        def get(self, *_args, **_kwargs):
            return "answered"

    session = _MeteredSession(Inner(), "immobiliare", budget)

    assert session.get("https://example.invalid/") == "answered"
    with pytest.raises(_BudgetExhausted) as refusal:
        session.get("https://example.invalid/")
    assert "request cap reached" in refusal.value.reason


# --- the paid provider --------------------------------------------------


def test_the_paid_rung_needs_paid(scraper):
    budget = a_budget(paid=False)
    rung = a_rung("api:scrapfly", [Fetched(status=200, body=PAGE_HTML)], direct=False, paid=True)

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert attempt.skipped == "the paid rung needs --paid"
    assert budget.credits_spent == 0


def test_the_paid_rung_stops_at_the_credit_cap(scraper):
    budget = a_budget(paid=True, max_credits=CREDITS_PER_PAGE, credit_floor=0)
    rung = a_rung(
        "api:scrapfly",
        [Fetched(status=200, body=API_NEXT, credits=25), Fetched(status=200, body=PAGE_HTML)],
        direct=False,
        paid=True,
    )

    attempts = run_rungs("immobiliare", scraper, [api_target(), html_target()], [rung], budget)

    assert attempts[0].outcome == "ok"
    assert attempts[0].credits == 25
    assert attempts[1].outcome == "skipped"
    assert attempts[1].skipped == "credit cap reached (--max-credits 25, 25 spent)"


def test_the_paid_rung_refuses_below_the_account_floor(scraper):
    budget = a_budget(paid=True, credit_floor=500)
    rung = a_rung(
        "api:scrapfly",
        [Fetched(status=200, body=PAGE_HTML)],
        direct=False,
        paid=True,
        remaining_credits=120,
    )

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert "120 credits left, below the floor (--credit-floor 500)" in attempt.skipped
    assert budget.credits_spent == 0


def test_an_unknown_balance_is_refused_rather_than_assumed(scraper):
    budget = a_budget(paid=True, credit_floor=500)
    rung = a_rung("api:scrapfly", [Fetched(status=200, body=PAGE_HTML)], direct=False, paid=True)

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert "did not report its remaining credits" in attempt.skipped


def test_the_floor_can_be_waived_with_zero(scraper):
    budget = a_budget(paid=True, credit_floor=0)
    rung = a_rung("api:scrapfly", [Fetched(status=200, body=PAGE_HTML)], direct=False, paid=True)

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert attempt.outcome == "ok"


def test_a_paid_call_that_brought_nothing_back_is_still_charged(scraper):
    """The finding this rule was written for: Scrapfly calls that timed out on
    the client side came back empty and were billed all the same."""
    budget = a_budget(paid=True, credit_floor=0, max_credits=100)
    rung = a_rung(
        "api:scrapfly",
        [Fetched(error="curl: (28) Operation timed out after 30005 milliseconds")],
        direct=False,
        paid=True,
    )

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], budget)

    assert attempt.outcome == "error"
    assert budget.credits_spent == CREDITS_PER_PAGE


def test_the_two_ledgers_do_not_touch(scraper):
    """Three refusals from this address must not cancel the paid rung: it is the
    one rung the run is there to price, and it does not leave from here."""
    budget = a_budget(paid=True, credit_floor=0)
    for index in range(BLOCKED_STREAK_LIMIT):
        run_rungs(
            "immobiliare",
            scraper,
            [html_target()],
            [a_rung(f"curl:p{index}", [Fetched(status=403)])],
            budget,
        )
    paid = a_rung(
        "api:scrapfly", [Fetched(status=200, body=API_NEXT, credits=25)], direct=False, paid=True
    )

    (attempt,) = run_rungs("immobiliare", scraper, [api_target()], [paid], budget)

    assert attempt.outcome == "ok"
    assert attempt.listings == 2


# --- what the parsers made of it ----------------------------------------


def test_the_api_next_body_goes_through_the_real_parser(scraper):
    rung = a_rung("curl:safari184", [Fetched(status=200, body=API_NEXT)])

    (attempt,) = run_rungs("immobiliare", scraper, [api_target()], [rung], a_budget())

    assert attempt.outcome == "ok"
    assert attempt.listings == 2
    assert attempt.strategy == "api-next"
    assert attempt.declared_total == 812
    assert [s["title"] for s in attempt.samples] == [
        "Bilocale zona Bicocca",
        "Trilocale via Chiese",
    ]
    assert attempt.samples[0]["price"] == 199000


def test_the_html_body_goes_through_the_real_cascade(scraper):
    rung = a_rung("curl:safari184", [Fetched(status=200, body=PAGE_HTML)])

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], a_budget())

    assert attempt.listings == 1
    assert attempt.strategy == "json-ld"
    assert attempt.bytes > 0


def test_nothing_matched_needs_the_portals_own_zero(scraper):
    """An empty list is not a proven `no_results`: with no count beside it the
    honest verdict is that the answer could not be read (invariant 26)."""
    budget = a_budget()
    counted = a_rung("curl:a", [Fetched(status=200, body=json.dumps({"count": 0, "results": []}))])
    bare = a_rung("curl:b", [Fetched(status=200, body=json.dumps({"results": []}))])

    (with_count,) = run_rungs("immobiliare", scraper, [api_target()], [counted], budget)
    (without_count,) = run_rungs("immobiliare", scraper, [api_target()], [bare], budget)

    assert with_count.outcome == "no_results"
    assert without_count.outcome == "error"


def test_an_unreadable_body_is_an_error_not_a_crash(scraper):
    rung = a_rung("curl:safari184", [Fetched(status=200, body="{not json at all")])

    (attempt,) = run_rungs("immobiliare", scraper, [api_target()], [rung], a_budget())

    assert attempt.outcome == "error"
    assert "the parser could not read it" in attempt.error


def test_a_transport_that_raised_is_reported_as_that_rungs_failure(scraper):
    def explode(_target):
        raise ConnectionError("connection reset by peer")

    rung = Rung(name="curl:safari184", fetch=explode)

    (attempt,) = run_rungs("immobiliare", scraper, [html_target()], [rung], a_budget())

    assert attempt.outcome == "error"
    assert "ConnectionError: connection reset by peer" in attempt.error


# --- nothing quotable ever leaves ---------------------------------------


def test_the_provider_key_never_reaches_the_report(scraper, tmp_path):
    """The one test here that would make the whole module a liability if it
    failed: the key rides in a query string and in the provider's own error text."""
    budget = a_budget(paid=True, credit_floor=0)
    target = Target(
        name="html p1",
        url=f"https://api.scrapfly.io/scrape?key={FAKE_KEY}&url=https%3A%2F%2Fimmobiliare.it%2F",
        kind="html",
    )
    rung = a_rung(
        "api:scrapfly",
        [Fetched(status=422, error=f"the provider refused: key {FAKE_KEY} is out of credit")],
        direct=False,
        paid=True,
    )

    attempts = run_rungs(
        "immobiliare", scraper, [target], [rung], budget, secrets=[FAKE_KEY, "a-cookie-value"]
    )
    run = Run(
        started_at="now",
        network="live",
        targets=[target.url],
        budget=budget.as_dict(),
        attempts=attempts,
    )
    path = write_report(new_run_directory(tmp_path), run, secrets=[FAKE_KEY])

    written = path.read_text(encoding="utf-8")
    assert FAKE_KEY not in written
    assert "key=***" in written
    assert FAKE_KEY not in render(run)


def test_redaction_catches_a_key_nobody_declared():
    """A pattern as well as a list: a report is written by code that did not
    necessarily know which parameter carried the credential."""
    assert redact("https://x.test/?api_key=abcdefghijkl&z=1") == "https://x.test/?api_key=***&z=1"
    assert redact("Bearer token=abcdefghijkl") == "Bearer token=***"
    # Short values are left alone, or half the report would be asterisks.
    assert redact("sorted by key=asc") == "sorted by key=asc"


def test_a_declared_secret_is_removed_from_free_text():
    assert redact(f"failed with {FAKE_KEY}", [FAKE_KEY]) == "failed with ***"


# --- the table and the verdict ------------------------------------------


def test_the_table_prints_no_number_it_did_not_measure():
    measured = Attempt(portal="immobiliare", rung="curl:a", target="html p1", declared_total=0)
    silent = Attempt(portal="immobiliare", rung="curl:b", target="html p1")

    header, first, second = render_table([measured, silent]).splitlines()

    assert "DECLARED" in header
    assert "0" in first
    assert "0" not in second


def test_the_verdict_names_the_rung_that_worked(scraper):
    budget = a_budget(paid=True, credit_floor=0)
    attempts = run_rungs(
        "immobiliare",
        scraper,
        [html_target()],
        [a_rung("curl:safari184", [Fetched(status=403)])],
        budget,
    )
    attempts += run_rungs(
        "immobiliare",
        scraper,
        [api_target()],
        [
            a_rung(
                "api:scrapfly",
                [Fetched(status=200, body=API_NEXT, credits=25)],
                direct=False,
                paid=True,
            )
        ],
        budget,
    )
    run = Run(started_at="now", network="live", targets=[SEARCH_URL], budget={}, attempts=attempts)

    verdict = verdicts(run)["immobiliare"]

    assert "works via api:scrapfly" in verdict
    assert "25 credits" in verdict
    assert "refused (403)" in verdict
    assert succeeded(run)


def test_a_portal_no_rung_reached_fails_the_run(scraper):
    attempts = run_rungs(
        "immobiliare",
        scraper,
        [html_target()],
        [a_rung("curl:safari184", [Fetched(status=403)])],
        a_budget(),
    )
    run = Run(started_at="now", network="live", targets=[SEARCH_URL], budget={}, attempts=attempts)

    assert verdicts(run)["immobiliare"].startswith("immobiliare: no rung worked")
    assert not succeeded(run)


def test_a_proven_empty_search_is_a_working_portal(scraper):
    attempts = run_rungs(
        "immobiliare",
        scraper,
        [api_target()],
        [a_rung("curl:a", [Fetched(status=200, body=json.dumps({"count": 0, "results": []}))])],
        a_budget(),
    )
    run = Run(started_at="now", network="live", targets=[SEARCH_URL], budget={}, attempts=attempts)

    assert "nothing matches this search" in verdicts(run)["immobiliare"]
    assert succeeded(run)


def test_resolving_the_geography_is_not_a_working_portal(scraper):
    # The first live run against Bicocca was refused by every transport and
    # still reported "works via prepare (geography)": the lookup endpoint that
    # builds the api-next parameters answered, and a setup step was allowed to
    # stand in for a page nobody got.
    attempts = [
        Attempt(portal="immobiliare", rung="prepare", target="geography", kind="prepare"),
    ]
    attempts[0].resolved = True
    attempts += run_rungs(
        "immobiliare",
        scraper,
        [html_target()],
        [a_rung("curl:safari184", [Fetched(status=403)])],
        a_budget(),
    )
    run = Run(started_at="now", network="live", targets=[SEARCH_URL], budget={}, attempts=attempts)

    assert verdicts(run)["immobiliare"].startswith("immobiliare: no rung worked")
    assert "1 of" not in verdicts(run)["immobiliare"]
    assert not succeeded(run)


def test_a_run_that_checked_nothing_is_not_a_success():
    assert not succeeded(Run(started_at="now", network="live", targets=[], budget={}))


# --- choosing the rungs -------------------------------------------------


def test_the_browser_is_not_in_the_default_selection():
    chosen = select_rungs(named_rungs("curl:a", "curl+cookie", "browser", "api:scrapfly"), None)

    assert [r.name for r in chosen] == ["curl:a", "curl+cookie", "api:scrapfly"]


def test_a_family_name_selects_the_whole_family():
    chosen = select_rungs(named_rungs("curl:a", "curl:b", "curl+cookie", "api:scrapfly"), ["curl"])

    assert [r.name for r in chosen] == ["curl:a", "curl:b"]


def test_an_exact_name_selects_just_that_rung():
    chosen = select_rungs(named_rungs("curl:a", "curl+cookie", "browser"), ["browser"])

    assert [r.name for r in chosen] == ["browser"]


def test_every_way_out_of_this_machine_is_offered(scraper):
    rungs = build_rungs("immobiliare", scraper, a_budget(), settings={})
    names = [r.name for r in rungs]

    assert names[: len(scraper.impersonations)] == [f"curl:{n}" for n in scraper.impersonations]
    assert "curl+cookie" in names
    assert "browser" in names
    assert any(name.startswith("api:") for name in names)


def test_a_rung_that_cannot_run_here_says_why(scraper):
    by_name = {r.name: r for r in build_rungs("immobiliare", scraper, a_budget(), settings={})}

    assert by_name["curl+cookie"].unavailable == "no datadome_cookie is saved"
    # No provider key in the test settings, so there is no paid rung to offer.
    assert "no scrape-API provider is configured" in by_name["api:none"].unavailable


def test_a_saved_cookie_makes_the_cookie_rung_available(scraper):
    rungs = build_rungs(
        "immobiliare", scraper, a_budget(), settings={"datadome_cookie": "a-long-cookie-value"}
    )

    assert next(r for r in rungs if r.name == "curl+cookie").unavailable == ""


def test_idealista_is_offered_its_own_api():
    rungs = build_rungs("idealista", IdealistaScraper(), a_budget(), settings={})

    official = next(r for r in rungs if r.name == "official")
    assert official.kinds == ("official",)
    assert official.unavailable == "no Idealista API key is configured"


# --- the targets --------------------------------------------------------


def test_geography_resolves_once_and_every_rung_reuses_it(scraper):
    scraper.session = FakeGeoSession(MILANO_GEO)
    budget = a_budget()
    attempts: list[Attempt] = []

    targets = _immobiliare_targets(scraper, SEARCH_URL, budget, attempts)

    assert [t.name for t in targets] == ["api-next p1", "html p1"]
    assert "idComune=8042" in targets[0].url
    assert targets[0].url.endswith("pag=1")
    assert targets[0].referer == SEARCH_URL
    assert attempts[0].outcome == "ok"
    assert scraper.session.calls == 1
    assert budget.requests_made("immobiliare") == 1


def test_geography_that_resolved_nothing_leaves_only_the_html_page(scraper):
    scraper.session = FakeGeoSession([])
    budget = a_budget()
    attempts: list[Attempt] = []

    targets = _immobiliare_targets(scraper, SEARCH_URL, budget, attempts)

    assert [t.name for t in targets] == ["html p1"]
    assert attempts[0].outcome == "blocked"
    assert "resolved nothing" in attempts[0].error
    # Invariant 7: without geography, api-next is not asked for at all.
    assert budget.blocked_streak("immobiliare") == 1


def test_geography_refused_by_the_budget_is_not_counted_as_a_block(scraper):
    scraper.session = FakeGeoSession(MILANO_GEO)
    budget = a_budget(max_requests=0)
    attempts: list[Attempt] = []

    targets = _immobiliare_targets(scraper, SEARCH_URL, budget, attempts)

    assert [t.name for t in targets] == ["html p1"]
    assert attempts[0].outcome == "skipped"
    assert scraper.session.calls == 0
    assert budget.blocked_streak("immobiliare") == 0


# --- replay -------------------------------------------------------------


def test_replay_reproduces_the_parse_with_no_network_at_all(scraper, tmp_path, monkeypatch):
    directory = new_run_directory(tmp_path)
    rung = a_rung(
        "curl:safari184",
        [Fetched(status=200, body=API_NEXT), Fetched(status=200, body=PAGE_HTML)],
    )
    attempts = run_rungs(
        "immobiliare",
        scraper,
        [api_target(), html_target()],
        [rung],
        a_budget(),
        capture=_capture_writer(directory),
    )
    write_report(
        directory,
        Run(
            started_at="then",
            network="live",
            targets=[SEARCH_URL],
            budget={},
            attempts=attempts,
        ),
    )

    def no_sockets(*_args, **_kwargs):
        raise AssertionError("a replay must not open a socket")

    monkeypatch.setattr(socket, "socket", no_sockets)
    again = replay(directory)

    assert again.network == "replay"
    assert [a.listings for a in again.attempts] == [2, 1]
    assert [a.strategy for a in again.attempts] == ["api-next", "json-ld"]
    assert again.attempts[0].declared_total == 812
    assert succeeded(again)


def test_replay_says_so_when_an_attempt_captured_nothing(scraper, tmp_path):
    directory = new_run_directory(tmp_path)
    attempts = run_rungs(
        "immobiliare",
        scraper,
        [html_target()],
        [a_rung("curl:safari184", [Fetched(status=403)])],
        a_budget(),
        capture=_capture_writer(directory),
    )
    write_report(
        directory,
        Run(started_at="then", network="live", targets=[SEARCH_URL], budget={}, attempts=attempts),
    )

    again = replay(directory)

    assert again.attempts[0].skipped == "nothing was captured for this attempt"


# --- a whole run --------------------------------------------------------


def test_a_url_from_another_site_is_reported_not_guessed(tmp_path):
    run = run_checks(
        ["https://www.casa.it/vendita/milano/"], budget=a_budget(), out_root=tmp_path, settings={}
    )

    assert [a.portal for a in run.attempts] == ["unknown"]
    assert "no portal this tool can check" in run.attempts[0].error
    assert not succeeded(run)
    assert (Path(run.directory) / "report.json").exists()


def test_portal_of_reads_the_host_not_the_path():
    assert portal_of(SEARCH_URL) == "immobiliare"
    assert portal_of("https://www.idealista.it/vendita-case/milano/") == "idealista"
    assert portal_of("https://example.test/immobiliare.it/milano/") == ""
    assert portal_of("not a url at all") == ""


def test_the_saved_searches_are_read_read_only(tmp_path):
    db = tmp_path / "case.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE search_profiles (id INTEGER PRIMARY KEY, search_url TEXT, is_active INTEGER)"
    )
    conn.executemany(
        "INSERT INTO search_profiles (search_url, is_active) VALUES (?, ?)",
        [(SEARCH_URL, 1), ("https://www.idealista.it/vendita-case/roma/", 0)],
    )
    conn.commit()
    conn.close()

    assert active_profiles(db) == [SEARCH_URL]
    # A read-only open leaves no journal behind next to the owner's database.
    assert not (tmp_path / "case.db-wal").exists()


def test_no_saved_database_is_no_profiles(tmp_path):
    assert active_profiles(tmp_path / "nothing-here.db") == []
