"""Fixtures shared by the whole suite.

The tests are meant to be offline and reproducible, but two module-level globals
reach out to the developer's own machine unless every test is pointed elsewhere:

- `load_settings()` reads `backend/settings.json` from disk — so the moment a
  developer configured real Gmail credentials there,
  `test_disabled_channels_send_nothing` stopped testing "disabled channels": it
  logged into smtp.gmail.com and delivered an actual email.
- `database.py` builds its engine from `DB_PATH` at import time, so anything
  reaching it lands in the real `case.db` — creating it on a clean machine, and
  on a developed one running `deduplicate_search_profiles` over the user's
  actual searches.

Point every test at throwaway copies of both, so the defaults apply and neither
a real credential nor real data is ever reachable from a test run.

A third global reaches further still: a scan now ends by asking Nominatim about
the listings it could not place from what it already knew, so any test driving
`run_scan` would send real requests to OpenStreetMap. `_offline_geocoder` shuts
that door for the whole suite; the tests that mean to exercise a lookup replace
the same symbol with their own stub, as they always have.

And two more are deliberately in memory rather than in the database — what a
scan is doing, and what the last few did — so they survive a test the way they
survive a scan, and a run's assertions would otherwise depend on which file
happened to drive a scan before it.
"""

import pytest

from app import config, database
from app.services import geocoder, scanner


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Repoint the database at a per-test file.

    One symbol is enough: `SessionLocal` resolves `database.engine` on every
    call, so redirecting the engine redirects every session with it — including
    the ones `init_db()` opens at the end of its own run, and the ones `scanner`
    and `scheduler` open through their `from ..database import SessionLocal`.
    While the factory was bound at import instead, this fixture had to patch
    both names, and even then the two from-importers were out of its reach.

    `make_engine` rather than a hand-built engine, so tests run against the same
    PRAGMAs (WAL, busy_timeout) as production.
    """
    engine = database.make_engine(f"sqlite:///{tmp_path / 'case.db'}")
    monkeypatch.setattr(database, "engine", engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _offline_geocoder(monkeypatch):
    """No test reaches Nominatim unless it says so.

    Raising rather than returning None is deliberate: `geocode()` treats an
    exception as transient and caches nothing, so a stray lookup leaves no trace
    in the test's database and cannot quietly change what a later assertion
    sees. A test that wants a lookup overrides this the ordinary way, and its
    `monkeypatch.setattr` wins because it runs after this fixture.
    """

    def refuse(*args, **kwargs):
        raise ConnectionError("the test suite never reaches Nominatim")

    monkeypatch.setattr(geocoder, "_nominatim_lookup", refuse)


@pytest.fixture(autouse=True)
def _empty_scan_report():
    """Every test starts with no scan in flight and an empty journal."""
    scanner._journal.clear()
    scanner._set_progress(reset=True)
