"""The whole flow, end to end, against the offline sandbox.

scrape -> normalize -> deduplicate -> notify, driven through `run_scan` with
the portals and the mail server on loopback. Every other test in this suite
substitutes one of those legs; this one substitutes none of them, so it is the
only place where the seams get exercised: the warm-up, the api-next request the
scanner really issues, the heuristic card boundary on a real HTTP response, and
the SMTP conversation `notifier` really holds.

The shared flat's numbers are the JSON-LD fixture's in `test_scrapers.py` —
Torino, Via Verdi 10, 95 m², 3 locali, 250.000 € — so the sandbox publishes a
property each parser has already been proven able to read, rather than a fresh
one whose failures could be the fixture's fault.
"""

from dataclasses import replace
from urllib.parse import urlparse

import pytest
from sqlalchemy import select

from app import config, database
from app.models import Property, SearchProfile
from app.scrapers.probe import AdProbe
from app.services import scanner

from . import mock_portal
from .mock_portal import Flat, MockPortalServer, MockSMTPServer

# Search URLs shaped exactly like the portals' own, because both scrapers read
# them: Immobiliare derives idContratto and the location to resolve from the
# path, Idealista derives the city from it ("municipality-province").
IMMOBILIARE_SEARCH = "/vendita-case/torino/"
IDEALISTA_SEARCH = "/vendita-case/torino-torino/"

# One apartment, two agencies, two portals. The two renderings expose the
# address by different means on purpose — Immobiliare in a structured
# `location.address`, Idealista only inside the title — which is exactly why
# the merge has to go through `street_and_civic` normalization to happen at all.
SHARED_ON_IMMOBILIARE = Flat(
    ad_id="12345",
    title="Trilocale via Verdi",
    price=250_000,
    rooms=3,
    sqm=95,
    city="Torino",
    zone="Centro",
    street="Via Verdi",
    civic="10",
    latitude=45.07,
    longitude=7.68,
    agency="Agenzia Rossi",
    description="Trilocale luminoso in palazzo d'epoca",
)
SHARED_ON_IDEALISTA = replace(
    SHARED_ON_IMMOBILIARE,
    ad_id="88888",
    title="Trilocale in vendita in Via Verdi, 10, Centro, Torino",
    agency="Studio Bianchi",
)

# A second Idealista card. It is not there for its own sake: the heuristic card
# boundary is "the last ancestor holding only one ad", so a one-card page has no
# boundary to find (invariant 2). It doubles as the check that conservative
# deduplication leaves it alone — 60 m² against 95 must never fold in.
OTHER_ON_IDEALISTA = Flat(
    ad_id="99999",
    title="Bilocale in vendita in Via Po, 4, Vanchiglia, Torino",
    price=180_000,
    rooms=2,
    sqm=60,
    city="Torino",
    zone="Vanchiglia",
    street="Via Po",
    civic="4",
)

# Appears on Immobiliare only on the second scan: the first scan is the silent
# baseline (invariant 3), so a notification needs something that arrives after it.
ARRIVAL_ON_IMMOBILIARE = Flat(
    ad_id="54321",
    title="Quadrilocale con terrazzo",
    price=420_000,
    rooms=4,
    sqm=120,
    city="Torino",
    zone="Crocetta",
    street="Corso Duca degli Abruzzi",
    civic="15",
    latitude=45.06,
    longitude=7.66,
    agency="Immobiliare Torino",
    description="Quadrilocale luminoso con ampio terrazzo",
)


@pytest.fixture
def portal():
    with MockPortalServer() as server:
        yield server


@pytest.fixture
def mailbox():
    with MockSMTPServer() as server:
        yield server


@pytest.fixture
def sandbox(portal, mailbox, monkeypatch):
    """Portals on loopback HTTP, notifications on loopback SMTP, nothing else
    reachable. The database and settings are already per-test (conftest)."""
    portal.install(monkeypatch)
    mock_portal.block_external_network(monkeypatch)
    database.Base.metadata.create_all(database.engine)
    config.save_settings(
        {
            # Email is the captured channel because it needs no patching at
            # all: host and port are settings. Telegram stays off, which is
            # also what keeps its hardcoded api.telegram.org out of the run.
            "email_enabled": True,
            "smtp_host": "127.0.0.1",
            "smtp_port": mailbox.port,
            "email_from": "bot@localhost",
            "email_to": "me@localhost",
            "telegram_enabled": False,
            # One page, no pacing: the sandbox answers instantly, and the
            # polite delay between pages is 8s on Idealista alone.
            "max_pages_per_search": 1,
            "request_delay_seconds": 0,
        }
    )


def _publish(portal, *, immobiliare: list[Flat], idealista: list[Flat]) -> None:
    """Put today's listings on both portals, each on its own primary path:
    api-next for Immobiliare, a heuristic HTML grid for Idealista."""
    portal.serve_json(
        "/api-next/geography/autocomplete/",
        mock_portal.immobiliare_geography(),
    )
    portal.serve_json(
        "/api-next/search-list/listings/",
        mock_portal.immobiliare_api_page(immobiliare),
    )
    portal.serve(IDEALISTA_SEARCH, mock_portal.idealista_results_page(idealista))


def _add_profiles(portal) -> None:
    db = database.SessionLocal()
    try:
        db.add(
            SearchProfile(
                name="Torino - Immobiliare",
                portal="immobiliare",
                search_url=portal.url(IMMOBILIARE_SEARCH),
            )
        )
        db.add(
            SearchProfile(
                name="Torino - Idealista",
                portal="idealista",
                search_url=portal.url(IDEALISTA_SEARCH),
            )
        )
        db.commit()
    finally:
        db.close()


def _properties() -> list[Property]:
    db = database.SessionLocal()
    try:
        props = list(db.scalars(select(Property).order_by(Property.id)))
        for prop in props:  # touch the relationship before the session closes
            len(prop.listings)
        return props
    finally:
        db.close()


def test_scrape_normalize_deduplicate_notify_with_no_network(portal, mailbox, sandbox):
    _publish(
        portal,
        immobiliare=[SHARED_ON_IMMOBILIARE],
        idealista=[SHARED_ON_IDEALISTA, OTHER_ON_IDEALISTA],
    )
    _add_profiles(portal)

    first = scanner.run_scan()

    # The baseline pass acquires but never announces (invariant 3). Two new
    # properties: the shared flat, and Idealista's second card.
    assert first["new"] == 2, first
    assert first["updated"] == 1, first  # the shared flat, found again on Idealista
    assert mailbox.messages == []

    # --- deduplicate: one flat, two portals, one card ---
    props = _properties()
    assert len(props) == 2
    shared, other = props
    assert {l.portal for l in shared.listings} == {"immobiliare", "idealista"}
    assert (shared.sqm, shared.rooms, shared.current_min_price) == (95.0, 3, 250_000)
    assert shared.city == "Torino"
    # 60 m² against 95: the conservative rules must leave it standing alone
    assert len(other.listings) == 1
    assert other.sqm == 60.0

    # --- notify: a listing that arrives after the baseline ---
    _publish(
        portal,
        immobiliare=[SHARED_ON_IMMOBILIARE, ARRIVAL_ON_IMMOBILIARE],
        idealista=[SHARED_ON_IDEALISTA, OTHER_ON_IDEALISTA],
    )
    second = scanner.run_scan()

    assert second["new"] == 1, second
    assert second["notified"] == 1, second
    assert len(mailbox.messages) == 1
    delivered = mailbox.texts()[0]
    assert "Quadrilocale con terrazzo" in delivered
    assert "420.000" in delivered
    assert "immobiliare" in delivered

    # --- no network: every page the scrapers fetched came from the sandbox ---
    paths = {urlparse(p).path for p in portal.requested}
    assert "/immobiliare-home" in paths  # warm-up, both portals
    assert "/idealista-home" in paths
    assert "/api-next/geography/autocomplete/" in paths  # invariant 7: geo resolved first
    assert "/api-next/search-list/listings/" in paths
    assert IDEALISTA_SEARCH in paths


def test_the_sandbox_serves_the_portals_over_real_http(portal, sandbox):
    """A portal page is fetched with `AdProbe`, never a hand-rolled client.

    `docs/conventions.md` makes that the rule for a live check, because AdProbe carries
    the tuned impersonation and the user's real cookie. It is the rule here for
    the cheaper reason: one HTTP path in the project means the sandbox is
    exercising the transport the scrapers use, not a second one that happens to
    agree with it today.
    """
    url = portal.serve("/annunci/12345/", "<html><body>Trilocale via Verdi</body></html>")

    assert "Trilocale via Verdi" in AdProbe().fetch(url)
    assert urlparse(portal.requested[-1]).path == "/annunci/12345/"
