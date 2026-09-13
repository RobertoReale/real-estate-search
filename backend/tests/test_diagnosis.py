"""The "try this search" diagnosis, offline.

Nothing here reaches a portal: `run_checks` is the seam, and every test replaces
it with a run it wrote itself. What is actually under test is the layer around
the harness — which rungs it is allowed to climb, what a diagnosis may cost, how
often it may be asked for, and the translation of the harness's sentences into
the codes the browser turns back into Italian.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config, main
from app.database import Base, get_db
from app.livecheck import budget as budget_module
from app.livecheck.report import Attempt, Run
from app.livecheck.rungs import build_rungs, select_rungs
from app.models import ScraperHealthSnapshot, SearchProfile
from app.scrapers.idealista import IdealistaScraper
from app.services import diagnosis, scraper_health
from app.services.scanner import scan_state

IMMOBILIARE = "https://www.immobiliare.it/vendita-case/milano/"


def a_budget(**kwargs) -> budget_module.Budget:
    """A budget that never really sleeps, so a whole run takes microseconds."""
    kwargs.setdefault("delay_seconds", 0.0)
    kwargs.setdefault("sleep", lambda _seconds: None)
    return budget_module.Budget(**kwargs)


def attempt(rung: str, **kwargs) -> Attempt:
    return Attempt(portal="immobiliare", rung=rung, target="html p1", **kwargs)


def a_run(*attempts: Attempt, credits_spent: int = 0) -> Run:
    return Run(
        started_at="2026-09-13T10:00:00",
        network="live",
        targets=[IMMOBILIARE],
        budget={},
        attempts=list(attempts),
        credits_spent=credits_spent,
    )


@pytest.fixture(autouse=True)
def _no_cooldown():
    """A cooldown is process-wide, so it would otherwise leak between tests."""
    diagnosis.forget_cooldowns()
    yield
    diagnosis.forget_cooldowns()


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_db
    session = Session()
    session.add(
        SearchProfile(name="Milano", portal="immobiliare", search_url=IMMOBILIARE, is_active=True)
    )
    session.commit()
    session.close()
    # no `with`: entering the context manager would run the lifespan, and with it
    # the scheduler the rest of the suite is careful never to start
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def ran(monkeypatch):
    """Drive the route with a run of our own, and keep what it was asked for."""
    calls: list[dict] = []

    def install(run: Run):
        def fake(urls, **kwargs):
            calls.append({"urls": urls, **kwargs})
            return run

        monkeypatch.setattr(diagnosis, "run_checks", fake)
        return calls

    return install


# --- the table the panel shows ------------------------------------------


def test_every_rung_reports_itself(client, ran):
    ran(
        a_run(
            attempt("curl:chrome120", status=403, refused_status=True),
            attempt("curl+cookie", skipped="no datadome_cookie is saved"),
            attempt("api:none", skipped="no scrape-API provider is configured in settings"),
        )
    )
    body = client.post("/api/search-profiles/1/diagnose").json()

    assert [(r["rung"], r["outcome"], r["reason"]) for r in body["rungs"]] == [
        ("curl:chrome120", "blocked", "blocked"),
        ("curl+cookie", "skipped", "no_cookie"),
        ("api:none", "skipped", "no_api_key"),
    ]
    assert body["rungs"][0]["status"] == 403
    assert body["advice"] == "blocked"
    assert body["profile_id"] == 1 and body["portal"] == "immobiliare"
    assert body["cooldown_seconds"] == diagnosis.COOLDOWN_SECONDS


def test_a_rung_that_worked_names_itself_in_the_advice(client, ran):
    ran(
        a_run(
            attempt("curl:chrome120", status=403, refused_status=True),
            attempt("curl+cookie", status=200, listings=25),
        )
    )
    body = client.post("/api/search-profiles/1/diagnose").json()

    assert body["advice"] == "works"
    assert body["winner"] == "curl+cookie"
    assert body["rungs"][1]["listings"] == 25


def test_a_portal_that_answers_nothing_is_not_a_failure(client, ran):
    ran(a_run(attempt("curl:chrome120", status=200, no_results=True)))
    body = client.post("/api/search-profiles/1/diagnose").json()

    assert body["advice"] == "no_results"
    assert body["rungs"][0]["outcome"] == "no_results"


def test_geography_alone_cannot_say_the_search_works(client, ran):
    """The lookup is a request and is reported as one, but it succeeds against an
    endpoint anti-bot rarely guards — report.py's rule, applied to the advice."""
    ran(
        a_run(
            Attempt(
                portal="immobiliare",
                rung="prepare",
                target="geography",
                kind="prepare",
                resolved=True,
            ),
            attempt("curl:chrome120", status=403, refused_status=True),
        )
    )
    body = client.post("/api/search-profiles/1/diagnose").json()

    assert body["advice"] == "blocked"
    assert [r["rung"] for r in body["rungs"]] == ["prepare", "curl:chrome120"]


def test_a_run_where_nothing_could_be_tried_says_so(client, ran):
    ran(a_run(attempt("curl+cookie", skipped="no datadome_cookie is saved")))
    assert client.post("/api/search-profiles/1/diagnose").json()["advice"] == "nothing_tried"


# --- the limits ----------------------------------------------------------


def test_one_diagnosis_per_search_every_ten_minutes(client, ran):
    ran(a_run(attempt("curl:chrome120", status=200, listings=3)))

    assert client.post("/api/search-profiles/1/diagnose").status_code == 200
    refused = client.post("/api/search-profiles/1/diagnose")
    assert refused.status_code == 429
    assert "diagnosed recently" in refused.json()["detail"]


def test_the_cooldown_expires(client, ran):
    ran(a_run(attempt("curl:chrome120", status=200, listings=3)))
    client.post("/api/search-profiles/1/diagnose")

    assert diagnosis.cooldown_left(1) > 0
    later = diagnosis._last_at[1] + diagnosis.COOLDOWN_SECONDS + 1
    assert diagnosis.cooldown_left(1, now=later) == 0


def test_a_scan_in_flight_refuses_the_diagnosis(client, ran):
    """Two things asking the same portal from the same address is the retry loop
    invariant 8 forbids, spread over two features."""
    ran(a_run(attempt("curl:chrome120", status=200, listings=3)))
    scan_state["running"] = True
    try:
        assert client.post("/api/search-profiles/1/diagnose").status_code == 409
    finally:
        scan_state["running"] = False
    assert diagnosis.cooldown_left(1) == 0


def test_an_unknown_search_is_a_404(client, ran):
    ran(a_run())
    assert client.post("/api/search-profiles/999/diagnose").status_code == 404


def test_the_request_cap_is_below_the_harness_default(client, ran):
    calls = ran(a_run(attempt("curl:chrome120", status=200, listings=3)))
    client.post("/api/search-profiles/1/diagnose")

    assert calls[0]["budget"].max_requests == diagnosis.MAX_REQUESTS
    assert diagnosis.MAX_REQUESTS < budget_module.DEFAULT_MAX_REQUESTS
    assert calls[0]["urls"] == [IMMOBILIARE]


# --- invariant 18: the browser is opt-in ---------------------------------


def test_the_browser_rung_is_left_out_unless_a_browser_is_wanted():
    assert "browser" not in diagnosis.rung_filter({})
    for key in diagnosis.BROWSER_SETTINGS:
        assert "browser" in diagnosis.rung_filter({key: True}), key


def test_the_named_filter_still_selects_every_free_rung():
    """Naming any rung replaces the harness's default selection, so the list has
    to name everything the diagnosis means to climb — including the paid rung,
    whose "not requested" row is a finding of its own."""
    scraper = IdealistaScraper()
    rungs = build_rungs("idealista", scraper, a_budget(), settings={})
    chosen = [r.name for r in select_rungs(rungs, diagnosis.rung_filter({}))]

    assert chosen == [f"curl:{name}" for name in scraper.impersonations] + [
        "curl+cookie",
        "api:none",
        "official",
    ]
    with_browser = select_rungs(rungs, diagnosis.rung_filter({"datadome_auto_refresh": True}))
    assert "browser" in [r.name for r in with_browser]


# --- the money -----------------------------------------------------------


def test_the_paid_rung_is_not_asked_for_by_default(client, ran):
    calls = ran(a_run(attempt("curl:chrome120", status=200, listings=3)))
    body = client.post("/api/search-profiles/1/diagnose").json()

    assert calls[0]["budget"].paid is False
    assert body["paid"] is False


def test_the_paid_rung_runs_only_when_the_flag_asks_for_it(client, ran):
    calls = ran(a_run(attempt("api:scrapfly", status=200, listings=25, credits=25)))
    body = client.post("/api/search-profiles/1/diagnose", json={"paid": True}).json()

    assert calls[0]["budget"].paid is True
    assert calls[0]["budget"].max_credits == budget_module.CREDITS_PER_PAGE
    assert body["paid"] is True


def test_the_paid_rung_stops_at_the_month_ceiling(client, ran):
    """R.2's ceiling, read from the ledger the scans spend from."""
    config.save_settings({"scrape_api_monthly_credits": 100})
    db = next(main.app.dependency_overrides[get_db]())
    today = datetime.now(UTC).date()
    db.add(ScraperHealthSnapshot(captured_on=today, portal="immobiliare", api_credits=100))
    db.commit()

    calls = ran(a_run(attempt("api:scrapfly", skipped="the paid rung needs --paid")))
    body = client.post("/api/search-profiles/1/diagnose", json={"paid": True}).json()

    assert calls[0]["budget"].paid is False
    assert body["paid"] is False
    assert body["rungs"][0]["reason"] == "budget"


def test_what_a_paid_diagnosis_spent_reaches_the_ledger(client, ran):
    ran(a_run(attempt("api:scrapfly", status=200, listings=25, credits=25), credits_spent=25))
    client.post("/api/search-profiles/1/diagnose", json={"paid": True})

    db = next(main.app.dependency_overrides[get_db]())
    month = scraper_health.credits_this_month(db)
    assert month["spent"] == 25 and month["calls"] == 1
    # ...and it is not a scan: the block rate the health panel reports is about
    # scans, and a diagnosis must not move it
    assert [r.attempts for r in month["rows"]] == [0]


# --- the harness's sentences, as codes -----------------------------------


def test_every_reason_the_harness_can_skip_for_has_a_code():
    """A code the UI cannot translate reaches the screen as an identifier, so
    the mapping is checked against the strings the harness actually produces
    rather than against a list written beside it."""

    reasons = [
        r.unavailable
        for r in build_rungs("idealista", IdealistaScraper(), a_budget(), settings={})
        if r.unavailable
    ]
    reasons += [
        a_budget(max_requests=0).refuse_direct("immobiliare"),
        a_budget(paid=False).refuse_paid(None),
        a_budget(paid=True, max_credits=0).refuse_paid(10_000),
        a_budget(paid=True).refuse_paid(None),
        a_budget(paid=True).refuse_paid(1),
    ]
    streaky = a_budget()
    for _ in range(budget_module.BLOCKED_STREAK_LIMIT):
        streaky.record_outcome("immobiliare", blocked=True)
    reasons.append(streaky.refuse_direct("immobiliare"))
    assert reasons, "the harness produced no skip reasons to classify"
    assert all(diagnosis.skip_code(reason) != "skipped" for reason in reasons), [
        (r, diagnosis.skip_code(r)) for r in reasons
    ]


def test_a_reason_with_no_code_still_reaches_the_screen(client, ran):
    ran(a_run(attempt("curl:chrome120", skipped="something nobody has classified yet")))
    row = client.post("/api/search-profiles/1/diagnose").json()["rungs"][0]

    assert row["reason"] == "skipped"
    assert row["detail"] == "something nobody has classified yet"


def test_no_secret_reaches_the_table(client, ran):
    config.save_settings({"scrape_api_key": "sk-live-0123456789abcdef"})
    ran(a_run(attempt("api:scrapfly", error="refused for key=sk-live-0123456789abcdef")))

    payload = client.post("/api/search-profiles/1/diagnose").text
    assert "sk-live-0123456789abcdef" not in payload
    assert "***" in payload
