"""Engine-level guarantees: the SQLite PRAGMAs that make concurrency safe.

`check_same_thread=False` plus writers in six background modules (scanner,
geocoder, availability check, harvester, scheduler) and FastAPI's threadpool is
the recipe for intermittent `database is locked`. The PRAGMAs in
`database.make_engine` are what makes that workload safe, and they are easy to
lose in a refactor without anything noticing — the failure they prevent is
timing-dependent, so it surfaces in production rather than here.
"""

import threading

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import database
from app.database import Base
from app.models import SearchProfile


@pytest.fixture
def file_engine(tmp_path):
    """A real on-disk engine: WAL is meaningless for an in-memory database."""
    engine = database.make_engine(f"sqlite:///{tmp_path / 'case.db'}")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def test_connection_runs_in_wal_with_a_busy_timeout(file_engine):
    with file_engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        # NORMAL is 1: safe under WAL, and the reason a commit is not fsync-bound
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1


def test_pragmas_apply_to_every_pooled_connection(file_engine):
    """The listener is on "connect", so each pooled connection gets them.

    Running the PRAGMAs once at startup instead would leave busy_timeout at 0 on
    every connection the pool opens afterwards — and that is precisely the
    connection a background thread ends up with.
    """
    first = file_engine.connect()
    second = file_engine.connect()
    try:
        for conn in (first, second):
            assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    finally:
        first.close()
        second.close()


def test_concurrent_writers_do_not_raise_database_is_locked(file_engine):
    """Two threads writing at once must not produce an OperationalError.

    WAL still allows only one writer at a time; the point is that the loser
    *waits* for the lock (busy_timeout) instead of failing instantly, which is
    what the user met as an intermittent `database is locked`. The barrier makes
    the two threads start together, and each then commits repeatedly so the
    overlap is real contention rather than a hopeful single shot.
    """
    factory = sessionmaker(bind=file_engine, autoflush=False, expire_on_commit=False)
    ready = threading.Barrier(2, timeout=30)
    writes_each = 25
    errors: list[BaseException] = []

    def write(tag: str):
        try:
            ready.wait()
            for i in range(writes_each):
                with factory() as db:
                    db.add(
                        SearchProfile(
                            name=f"{tag}-{i}",
                            portal="immobiliare",
                            search_url=f"https://example.com/{tag}/{i}",
                        )
                    )
                    db.commit()
        except BaseException as exc:  # noqa: BLE001 - reported on the main thread
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(tag,)) for tag in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"concurrent writers raised: {errors!r}"
    with factory() as db:
        assert db.query(SearchProfile).count() == 2 * writes_each
