"""Measure the backend, so an efficiency claim can be checked instead of felt.

`docs/audit.md` §7 is the procedure; this is the instrument it runs. Nothing
here asserts anything — it prints numbers, and the numbers recorded in §7 are
what a later run is compared against. That split is deliberate: a wall clock is
not a gate (it would fail on a busy laptop and teach everyone to re-run it), but
a change that claims to make the scan faster has to name a before and an after,
and there has to be one instrument that produces both.

Three measurements, in the order §7 reads them:

* **the scan** — requests issued and wall time, against `tests/mock_portal.py`.
  The mock portal is the only honest offline stand-in for a portal: it answers
  real HTTP on loopback, paginates, and records when each request arrived. Three
  configurations, because what is worth knowing is not the absolute seconds (the
  sandbox answers instantly, a real portal does not) but what the last two
  phases of work bought — reading the two hosts at once, and stopping a routine
  scan once it recognises everything.
* **queries per request** — the statements each dashboard endpoint issues
  against the demo corpus. An N+1 is invisible until it is counted.
* **the plans** — `EXPLAIN QUERY PLAN` for the statements the grid issues, so
  "there is an index on that column" can be checked rather than assumed.

Run it from `backend/`, which is where the venv and the `app` package are:

    cd backend && .venv\\Scripts\\python ..\\scripts\\measure_backend.py

It touches nothing of the user's: settings and the database are redirected to a
temporary directory, and anything trying to leave the machine fails loudly —
the same offline guarantee the test suite runs under.
"""

import argparse
import contextlib
import shutil
import sys
import tempfile
import time
import typing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app import config, database  # noqa: E402
from app.models import SearchProfile  # noqa: E402
from app.services import geocoder, scanner  # noqa: E402
from tests import mock_portal  # noqa: E402
from tests.mock_portal import Flat, MockPortalServer  # noqa: E402

# One search per portal, paginated. Five pages is enough for the per-host pause
# to dominate the way it does on a real portal, and small enough that the whole
# instrument runs in well under a minute.
PAGES = 5
FLATS_PER_PAGE = 2
# Well below the 6s default: this measures the *shape* of the waiting rather
# than reproducing it, and at 6s a single configuration would take two minutes.
DELAY = 0.4

IMMOBILIARE_SEARCH = "/vendita-case/torino/"
IDEALISTA_SEARCH = "/vendita-case/torino-torino/"


class _Patch:
    """`monkeypatch.setattr`, without pytest.

    The sandbox is built for the suite and takes a monkeypatch object; this is
    the part of it `mock_portal` actually calls, so the instrument and the tests
    drive the same fixture rather than two copies of it.
    """

    def __init__(self) -> None:
        self._undo: list[tuple[typing.Any, str, typing.Any]] = []

    def setattr(self, target: typing.Any, name: str, value: typing.Any) -> None:
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self) -> None:
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


@contextlib.contextmanager
def _throwaway_data() -> typing.Iterator[Path]:
    """Settings and database pointed at a temp directory, restored afterwards.

    The same two globals `tests/conftest.py` redirects, and for the same reason:
    without it this reads the developer's real `settings.json` and writes into
    their real `case.db`.
    """
    tmp = Path(tempfile.mkdtemp(prefix="measure-backend-"))
    patch = _Patch()
    patch.setattr(config, "SETTINGS_PATH", tmp / "settings.json")
    engine = database.make_engine(f"sqlite:///{tmp / 'case.db'}")
    patch.setattr(database, "engine", engine)
    try:
        yield tmp
    finally:
        engine.dispose()
        patch.undo()
        shutil.rmtree(tmp, ignore_errors=True)


def _refuse(*_args: typing.Any, **_kwargs: typing.Any) -> typing.NoReturn:
    raise ConnectionError("the measurement never reaches Nominatim")


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------


def _flats(portal: str, page: int) -> list[Flat]:
    # Numeric ad ids, because both parsers identify an ad by the digits in its
    # path (`/immobile/(\\d+)`, `/annunci/(\\d+)`): a readable "idealista-2-1"
    # is silently no ad at all, and the page reads as a markup change.
    # The two portals are kept a long way apart in price and surface so the
    # deduplicator has nothing to merge — this measures the walk, not the merge.
    lead = 10 if portal == "immobiliare" else 20
    return [
        Flat(
            ad_id=f"{lead}{page:02d}{i:02d}",
            title=f"{portal} page {page} flat {i}",
            price=(200_000 if lead == 10 else 700_000) + 1_000 * (2 * page + i),
            rooms=2 + (2 * page + i) % 3,
            sqm=(50 if lead == 10 else 200) + 3 * (2 * page + i),
            city="Torino",
            latitude=45.07,
            longitude=7.68,
        )
        for i in range(FLATS_PER_PAGE)
    ]


def _publish(portal: MockPortalServer) -> None:
    """Both portals, each paginated on the path its own scraper walks:
    Immobiliare in the query (`pag`), Idealista in the path (`/lista-N.htm`)."""
    portal.serve_json("/api-next/geography/autocomplete/", mock_portal.immobiliare_geography())
    portal.serve_json_pages(
        "/api-next/search-list/listings/",
        lambda page: mock_portal.immobiliare_api_page(
            _flats("immobiliare", page), max_pages=PAGES, count=FLATS_PER_PAGE * PAGES
        ),
    )
    portal.serve(IDEALISTA_SEARCH, mock_portal.idealista_results_page(_flats("idealista", 1)))
    for page in range(2, PAGES + 1):
        portal.serve(
            f"{IDEALISTA_SEARCH}lista-{page}.htm",
            mock_portal.idealista_results_page(_flats("idealista", page)),
        )


def _watch_both(portal: MockPortalServer) -> None:
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


def _per_host(paths: list[str]) -> dict[str, int]:
    """Requests per host, warm-up and geography lookup included — everything the
    portals were asked for, because everything they were asked for is a request
    an anti-bot system saw."""
    counts = {"immobiliare": 0, "idealista": 0}
    for path in paths:
        p = urlparse(path).path
        host = "immobiliare" if p.startswith(("/api-next", "/immobiliare")) else "idealista"
        counts[host] += 1
    return counts


def _one_scan(label: str, *, concurrent: bool, repeat: bool) -> None:
    with _throwaway_data():
        patch = _Patch()
        with MockPortalServer() as portal:
            portal.install(patch)
            mock_portal.block_external_network(patch)
            patch.setattr(geocoder, "_nominatim_lookup", _refuse)
            database.Base.metadata.create_all(database.engine)
            config.save_settings(
                {
                    "max_pages_per_search": PAGES,
                    "request_delay_seconds": DELAY,
                    "scan_portals_concurrently": concurrent,
                    "telegram_enabled": False,
                    "email_enabled": False,
                }
            )
            _publish(portal)
            _watch_both(portal)

            if repeat:
                # The first scan of a search is always a full sweep — there is
                # nothing yet to recognise — so the quick scan being measured is
                # the second one, which is the only kind a scheduled run makes
                # after day one.
                scanner.run_scan(manual=True)
            already = len(portal.requested)

            started = time.monotonic()
            summary = scanner.run_scan(manual=True)
            elapsed = time.monotonic() - started

            measured = portal.requested[already:]
            counts = _per_host(measured)
            print(
                f"  {label:<34} {len(measured):>3} requests "
                f"(imm {counts['immobiliare']}, ide {counts['idealista']})"
                f"   {elapsed:6.2f}s   new={summary['new']} updated={summary['updated']}"
            )
            patch.undo()


def measure_scan() -> None:
    """What a scan costs the portals, and what the last two phases bought.

    Read the three lines against each other and never on their own: the sandbox
    answers in microseconds where a portal takes a second, so the absolute wall
    clock says nothing about a real run. What it does say is that nearly all of
    a scan is the deliberate pause between pages — on the sandbox and on the
    real thing alike — and therefore that the only two ways to make one faster
    are to spend those pauses on two hosts at once (H.3) and to stop early when
    there is nothing new (H.4).
    """
    print(f"\n== the scan ==  {PAGES} pages/portal, {DELAY}s between pages, two portals")
    _one_scan("full sweep, one host at a time", concurrent=False, repeat=False)
    _one_scan("full sweep, both hosts at once", concurrent=True, repeat=False)
    _one_scan("quick scan, nothing new", concurrent=True, repeat=True)


# ---------------------------------------------------------------------------
# Queries per request, and the plans behind them
# ---------------------------------------------------------------------------

# What the dashboard actually asks for. `limit=0` is the map and "select all":
# the unbounded set, which is the shape every poll had before the grid was
# paginated, and so the honest worst case to keep an eye on.
ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("the grid, one page", "/api/properties?limit=50"),
    ("the grid, unbounded (map, select all)", "/api/properties?limit=0"),
    ("the poll, every 4s during a scan", "/api/scrapers/status"),
    ("one property's card", "/api/properties/{id}"),
    ("insights: market velocity", "/api/market-velocity"),
    ("insights: scraper health", "/api/scraper-health"),
    ("the searches page", "/api/search-profiles"),
)


def _explain(issued: list[tuple[str, typing.Any]]) -> list[tuple[str, str]]:
    """`EXPLAIN QUERY PLAN` for each distinct SELECT a request issued.

    Read it for the word SCAN. A full scan of `properties` is expected and fine
    at this size — the grid post-filters in Python by design, see
    `routers/selection.py` — but a scan of `listings` or `price_history` per
    property is the N+1 the query count above would already have shown.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    with database.engine.connect() as conn:
        for statement, parameters in issued:
            flat = " ".join(statement.split())
            if not flat.upper().startswith("SELECT") or flat in seen:
                continue
            seen.add(flat)
            try:
                rows = conn.exec_driver_sql(f"EXPLAIN QUERY PLAN {statement}", parameters).all()
            except Exception as e:  # a statement the driver will not re-run bare
                out.append((flat[:120], f"(could not explain: {type(e).__name__})"))
                continue
            out.append((flat[:120], "\n".join(str(row[-1]) for row in rows)))
    return out


def measure_queries() -> None:
    from fastapi.testclient import TestClient
    from sqlalchemy import event, select

    from app import main
    from app.database import get_db
    from app.models import Property
    from app.services.demo_data import seed_demo

    with _throwaway_data():
        patch = _Patch()
        patch.setattr(geocoder, "_nominatim_lookup", _refuse)
        database.Base.metadata.create_all(database.engine)
        db = database.SessionLocal()
        try:
            corpus = seed_demo(db)
            first = db.scalars(select(Property.id).limit(1)).one()
        finally:
            db.close()

        statements: list[tuple[str, typing.Any]] = []

        @event.listens_for(database.engine, "before_cursor_execute")
        def _record(_conn, _cursor, statement, parameters, _context, _many):  # noqa: ANN001
            statements.append((statement, parameters))

        def override_db():
            session = database.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        main.app.dependency_overrides[get_db] = override_db
        # no `with`: entering the context manager runs the lifespan, which starts
        # the real scheduler and would have this instrument scanning portals
        client = TestClient(main.app)

        print(
            f"\n== queries per request ==  demo corpus: {corpus.properties} properties, "
            f"{corpus.listings} listings, {corpus.profiles} searches"
        )
        plans: list[tuple[str, str]] = []
        for label, path in ENDPOINTS:
            statements.clear()
            resp = client.get(path.replace("{id}", str(first)))
            issued = list(statements)
            note = "" if resp.status_code == 200 else f"   !! HTTP {resp.status_code}"
            print(f"  {label:<38} {len(issued):>3} queries{note}")
            if path.endswith("limit=50"):
                plans = _explain(issued)

        main.app.dependency_overrides.clear()
        patch.undo()

        print("\n== query plans, for the statements the grid page issues ==")
        for statement, plan in plans:
            print(f"  {statement}")
            for line in plan.splitlines():
                print(f"      {line}")


def run() -> None:
    parser = argparse.ArgumentParser(description="Measure the backend (docs/audit.md §7).")
    parser.add_argument(
        "--only",
        choices=("scan", "queries"),
        help="run one of the two measurements instead of both",
    )
    args = parser.parse_args()
    print(f"backend measurement — {datetime.now(UTC):%Y-%m-%d %H:%M UTC}")
    if args.only != "queries":
        measure_scan()
    if args.only != "scan":
        measure_queries()


if __name__ == "__main__":
    run()
