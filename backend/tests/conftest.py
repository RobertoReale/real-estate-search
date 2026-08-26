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
"""

import pytest

from app import config, database


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
