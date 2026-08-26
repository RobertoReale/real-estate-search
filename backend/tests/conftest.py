"""Fixtures shared by the whole suite.

The tests are meant to be offline and reproducible, but two module-level globals
reach out to the developer's own machine unless every test is pointed elsewhere:

- `load_settings()` reads `backend/settings.json` from disk — so the moment a
  developer configured real Gmail credentials there,
  `test_disabled_channels_send_nothing` stopped testing "disabled channels": it
  logged into smtp.gmail.com and delivered an actual email.
- `database.py` builds its engine and session factory from `DB_PATH` at import
  time, so anything reaching them lands in the real `case.db` — creating it on a
  clean machine, and on a developed one running `deduplicate_search_profiles`
  over the user's actual searches.

Point every test at throwaway copies of both, so the defaults apply and neither
a real credential nor real data is ever reachable from a test run.
"""

import pytest
from sqlalchemy.orm import sessionmaker

from app import config, database


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Repoint the engine *and* the session factory at a per-test database.

    Patching only `database.engine` is not enough, and that gap is exactly what
    made six tests touch the real `case.db`: `SessionLocal` is bound to the
    engine at import time, so `init_db()`'s closing
    `with SessionLocal() as db: deduplicate_search_profiles(db)` kept opening the
    developer's database no matter which engine the test had installed.

    The replacement resolves `database.engine` on every call rather than
    capturing it here, because several tests install an engine of their own and
    then call `init_db()`. A factory bound once at fixture setup would send that
    final session to a different database than the one `init_db()` had just
    built its tables in.
    """
    engine = database.make_engine(f"sqlite:///{tmp_path / 'case.db'}")
    monkeypatch.setattr(database, "engine", engine)

    def _session_factory():
        return sessionmaker(bind=database.engine, autoflush=False, expire_on_commit=False)()

    monkeypatch.setattr(database, "SessionLocal", _session_factory)
    yield
    engine.dispose()
