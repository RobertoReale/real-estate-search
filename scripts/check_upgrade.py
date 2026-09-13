"""Take a real database through an upgrade, and prove the way back from it.

    python scripts/check_upgrade.py --db backend/backups/some-copy.db

This is the upgrade check of [docs/manual-tests.md](../docs/manual-tests.md) --
item 6 of the list a person used to run by hand -- with the parts a machine can
decide taken off their hands. What is left to do in the browser is clicking
through Settings and seeing the copies listed. Everything
underneath that -- the migration, the pre-upgrade snapshot, the rotation that must
not prune it, the curated fields surviving, download, restore, import -- is
mechanical, and this script does it against the one thing the offline suite can
never have: a database some earlier release actually wrote.

`test_migrations.py` starts from a database this repository created, which is why
it cannot answer the question. This script starts from a file named on the command
line and **never writes to it**. The working database is produced through the
sqlite3 backup API from a read-only connection, so an un-checkpointed WAL comes
along and the original is not opened for writing even once.

Everything happens in a throwaway data directory: `APP_DATA_DIR` points the app at
it before the app is imported, so the copies, the log and the settings land there
and nowhere near the user's own. The backend listens on 8139 -- never 8000, which
belongs to the running app.

Two things the script does deliberately, and says so in its output when it does:

* **It rewinds the copy's recorded schema revision** when that revision is already
  this build's head. `database._snapshot_before_upgrade` takes the `case-pre-*`
  copy only when a migration is actually going to run, so a database already at
  head correctly produces no snapshot -- and a check that accepted that would be
  checking nothing. Rewinding `alembic_version` on the *copy* gives the startup a
  genuine upgrade to perform; not one row of data is touched.
* **It holds the scan flag rather than starting a scan.** `restore` refuses while
  `scanner.scan_state["running"]` is set, and that flag is the whole of the lock
  the endpoint reads. Starting a real scan to raise it would send requests to the
  portals, which this script has no business doing (see docs/live-checks.md), and
  would make the refusal a race rather than an assertion. So the app runs
  in-process and the flag is held directly.

One `[PASS]` or `[FAIL]` line per assertion, a non-zero exit if any failed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

DEFAULT_PORT = 8139

# Columns on `properties` that hold something the user typed or decided, and that
# therefore cannot be rebuilt by re-scanning. The point of the comparison is that
# every one of them survives the migration byte for byte.
CURATED_PROPERTY_COLUMNS = ("is_favorite", "notes", "status", "sold_at", "gone_at")


class Report:
    """The pass/fail lines, and whether anything failed."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        # flushed, every line: the app logs to stderr on the same console, and an
        # unflushed stdout puts the whole report after it when the output is piped
        verdict = "PASS" if ok else "FAIL"
        print(f"[{verdict}] {label}" + (f" -- {detail}" if detail else ""), flush=True)
        if not ok:
            self.failures.append(label)
        return ok

    def note(self, text: str) -> None:
        print(f"[note] {text}", flush=True)

    def warn(self, text: str) -> None:
        print(f"[WARN] {text}", flush=True)


# --- reading a database without being able to change it ---


def _read_only(path: Path) -> sqlite3.Connection:
    """The same read-only URI form `services/backup.py` uses, and for the same
    reason: a plain connect() creates a missing file and may roll back a hot
    journal into one we were only asked to look at."""
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _copy_aside(source: Path, target: Path) -> None:
    """Produce a working copy through the sqlite3 backup API, reading the source
    read-only. A plain file copy would leave the WAL behind and would need the two
    companion files carried by hand -- the exact trap item 6 exists to retire."""
    with closing(_read_only(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')")}


def read_state(path: Path) -> dict:
    """Everything worth comparing across a migration: how many rows each table
    holds, and every curated value keyed by the fingerprint that identifies the
    property across schema changes."""
    with closing(_read_only(path)) as conn:
        tables = _tables(conn)
        counts = {
            t: conn.execute(f"SELECT count(*) FROM '{t}'").fetchone()[0]
            for t in sorted(tables)
            if t != "alembic_version"
        }
        revision = None
        if "alembic_version" in tables:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            revision = row[0] if row else None

        present = [c for c in CURATED_PROPERTY_COLUMNS if c in _columns(conn, "properties")]
        curated = {
            row[0]: tuple(row[1:])
            for row in conn.execute(f"SELECT fingerprint, {', '.join(present)} FROM properties")
        }
        tags: dict[str, list[str]] = {}
        for fingerprint, name in conn.execute(
            "SELECT p.fingerprint, t.name FROM property_tags pt "
            "JOIN properties p ON p.id = pt.property_id "
            "JOIN tags t ON t.id = pt.tag_id"
        ):
            tags.setdefault(fingerprint, []).append(name)
        history: dict[str, list[tuple]] = {}
        for fingerprint, old, new, when in conn.execute(
            "SELECT p.fingerprint, h.old_price, h.new_price, h.changed_at FROM price_history h "
            "JOIN properties p ON p.id = h.property_id"
        ):
            history.setdefault(fingerprint, []).append((old, new, when))

    return {
        "revision": revision,
        "counts": counts,
        "curated_columns": present,
        "curated": curated,
        "tags": {k: sorted(v) for k, v in tags.items()},
        "history": {k: sorted(v, key=repr) for k, v in history.items()},
    }


def alembic_head() -> str | None:
    """This build's newest revision, read the way the app reads it."""
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from app.database import ALEMBIC_DIR, ALEMBIC_INI  # noqa: PLC0415

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return ScriptDirectory.from_config(cfg).get_current_head()


def rewind_revision(path: Path, revision: str) -> None:
    """Rewrite only the copy's `alembic_version` row, so the startup after it has
    a migration to run. No table and no row of data is touched."""
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("UPDATE alembic_version SET version_num = ?", (revision,))
        conn.commit()


# --- the backend, in this process, on its own port ---


class Backend:
    """The app served by uvicorn on a thread of its own.

    In-process rather than as a subprocess for one reason: the restore guard reads
    an in-memory flag, and holding that flag is the only way to assert the refusal
    without sending a single request to a portal.
    """

    def __init__(self, port: int) -> None:
        self.port = port
        self._server = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        import uvicorn  # noqa: PLC0415 -- after APP_DATA_DIR is set, like every app import here

        from app.main import app  # noqa: PLC0415

        # The app logs every copy it writes, and fifteen of them would bury the
        # pass/fail lines this script exists to print. Only the console handler is
        # quietened: app.log in the throwaway data directory keeps everything, and
        # a warning (a snapshot that could not be written, say) still comes through.
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and not hasattr(handler, "baseFilename"):
                handler.setLevel(logging.WARNING)

        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def wait_until_ready(self, timeout: float = 120.0) -> None:
        """Poll a real route, not the docs page: it answers only once the lifespan
        has run, which is where init_db migrates."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server is not None and getattr(self._server, "started", False):
                status, _ = request(self.port, "GET", "/api/scrapers/status")
                if status == 200:
                    return
            time.sleep(0.25)
        raise RuntimeError(f"the backend did not answer on port {self.port} within {timeout:.0f}s")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=30)


def request(port: int, method: str, path: str, body: bytes | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/octet-stream")
    try:
        with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310 -- fixed loopback
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def json_request(
    port: int, method: str, path: str, body: bytes | None = None
) -> tuple[int, object]:
    status, payload = request(port, method, path, body)
    try:
        return status, json.loads(payload)
    except ValueError:
        return status, payload.decode("utf-8", "replace")


# --- the assertions ---


def compare_state(report: Report, before: dict, after: dict) -> None:
    """Row counts and every curated field, before the migration against after it."""
    shared = sorted(before["counts"])
    differing = {t: (before["counts"][t], after["counts"].get(t)) for t in shared}
    differing = {t: v for t, v in differing.items() if v[0] != v[1]}
    total = sum(before["counts"].values())
    report.check(
        not differing,
        "row counts unchanged by the migration",
        f"{len(shared)} tables, {total} rows" if not differing else f"differs: {differing}",
    )
    new_tables = sorted(set(after["counts"]) - set(before["counts"]))
    if new_tables:
        report.note(f"tables the migration added (empty, so not compared): {', '.join(new_tables)}")

    report.check(
        before["curated_columns"] == after["curated_columns"],
        "the curated columns still exist after the migration",
        ", ".join(after["curated_columns"]),
    )
    report.check(
        before["curated"] == after["curated"],
        "favourites, notes, hidden and sold flags unchanged",
        f"{len(before['curated'])} properties compared",
    )
    report.check(
        before["tags"] == after["tags"],
        "tags unchanged",
        f"{sum(len(v) for v in before['tags'].values())} tag links on "
        f"{len(before['tags'])} properties",
    )
    report.check(
        before["history"] == after["history"],
        "price history unchanged",
        f"{sum(len(v) for v in before['history'].values())} price points on "
        f"{len(before['history'])} properties",
    )
    if not before["curated"]:
        report.warn(
            "this database holds no properties, so the four comparisons above ran over "
            "zero curated rows. They prove the schema and the reference tables survived, "
            "not that a favourite did. Point --db at a database with a scan in it for that."
        )


def check_snapshot_and_rotation(
    report: Report, port: int, named_for: str, recorded: str | None
) -> str | None:
    """The pre-upgrade copy exists, and fifteen daily copies later it is still there."""
    status, listing = json_request(port, "GET", "/api/maintenance/backups")
    if not isinstance(listing, dict) or status != 200:
        report.check(False, "the backups folder can be listed", f"HTTP {status}: {listing!r}")
        return None
    pre = [c for c in listing["backups"] if c["kind"] == "pre-upgrade"]
    expected = f"case-pre-{named_for}.db"
    report.check(
        len(pre) == 1 and pre[0]["name"] == expected,
        "a pre-upgrade snapshot was taken before the schema changed",
        pre[0]["name"] if len(pre) == 1 else f"expected {expected}, found {len(pre)} snapshots",
    )
    if not pre:
        return None
    name = pre[0]["name"]
    report.check(
        pre[0]["revision"] == recorded,
        "the snapshot holds the schema the database had before the migration",
        f"records {pre[0]['revision']}",
    )

    for i in range(15):
        status, _ = json_request(port, "POST", "/api/maintenance/backups")
        if status != 200:
            report.check(False, "fifteen daily copies can be taken", f"#{i + 1}: HTTP {status}")
            return name
    status, listing = json_request(port, "GET", "/api/maintenance/backups")
    assert isinstance(listing, dict)
    daily = [c for c in listing["backups"] if c["kind"] == "daily"]
    still_there = [c for c in listing["backups"] if c["name"] == name]
    report.check(
        len(daily) == 14,
        "the daily rotation prunes itself to fourteen copies",
        f"{len(daily)} daily copies after taking fifteen",
    )
    report.check(
        bool(still_there),
        "the pre-upgrade snapshot survives the rotation",
        f"{name} still listed" if still_there else f"{name} was pruned",
    )
    return name


def check_download(report: Report, port: int, name: str, scratch: Path) -> None:
    """A copy fetched through the API is a plain SQLite database anything can read."""
    status, payload = request(port, "GET", f"/api/maintenance/backups/{name}")
    if status != 200:
        report.check(False, "a copy can be downloaded through the API", f"HTTP {status}")
        return
    downloaded = scratch / "downloaded.db"
    downloaded.write_bytes(payload)
    try:
        with closing(_read_only(downloaded)) as conn:
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            properties = conn.execute("SELECT count(*) FROM properties").fetchone()[0]
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.DatabaseError as e:
        report.check(False, "the downloaded copy opens in sqlite3", str(e))
        return
    report.check(
        integrity == "ok",
        "the downloaded copy opens in sqlite3 and passes quick_check",
        f"{len(payload)} bytes, schema {row[0] if row else 'none'}, {properties} properties",
    )


def check_restore(report: Report, port: int, name: str) -> None:
    """Refused while the scan flag is held, accepted when it is not."""
    from app.services.scanner import scan_state  # noqa: PLC0415

    scan_state["running"] = True
    try:
        status, body = json_request(port, "POST", f"/api/maintenance/backups/{name}/restore")
        report.check(
            status == 409, "restore is refused while a scan holds the lock", f"HTTP {status}"
        )
    finally:
        scan_state["running"] = False

    status, body = json_request(port, "POST", f"/api/maintenance/backups/{name}/restore")
    ok = status == 200 and isinstance(body, dict) and body.get("restored") == name
    report.check(
        ok,
        "restore succeeds when no scan is running",
        f"restored {body['restored']}, previous state kept as {body['backup']}"
        if ok and isinstance(body, dict)
        else f"HTTP {status}: {body!r}",
    )


def check_import(report: Report, port: int, source: Path) -> None:
    """A `case.db` carried from another install is filed, and outside the rotation."""
    status, body = json_request(
        port, "POST", "/api/maintenance/backups/import", source.read_bytes()
    )
    ok = status == 200 and isinstance(body, dict) and body.get("kind") == "imported"
    report.check(
        ok,
        "a database from another install can be imported",
        f"filed as {body['name']}, schema {body['revision']}"
        if ok and isinstance(body, dict)
        else f"HTTP {status}: {body!r}",
    )


# --- the run ---


def port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def run(source: Path, port: int, scratch: Path, report: Report) -> None:
    working = scratch / "case.db"
    print(f"source     {source}", flush=True)
    print(f"data dir   {scratch}", flush=True)
    print(f"backend    http://127.0.0.1:{port}", flush=True)
    print(flush=True)

    _copy_aside(source, working)
    report.check(working.exists(), "the database was copied into a throwaway data directory")
    # a second copy of the same file, for the import step at the end -- the copy
    # above is about to become the live database and cannot serve as both
    carried = scratch / "carried-from-another-install.db"
    _copy_aside(source, carried)

    # An instance whose only job is backups must never scan, whatever the copied
    # database has configured: the scheduler runs a catch-up scan on startup when
    # the last one is overdue, and a scan from here would reach the real portals.
    (scratch / "settings.json").write_text(json.dumps({"scanning_paused": True}), "utf-8")

    from app.database import BASELINE_REVISION  # noqa: PLC0415

    before = read_state(working)
    head = alembic_head()
    print(
        f"the copy records schema revision {before['revision']}; this build's head is {head}",
        flush=True,
    )
    if before["revision"] == head:
        report.note(
            f"the copy is already at head, so startup would migrate nothing and would "
            f"correctly take no snapshot. Rewinding the copy's recorded revision to "
            f"{BASELINE_REVISION} so the upgrade path runs for real; no data is touched."
        )
        rewind_revision(working, BASELINE_REVISION)
        before = read_state(working)
    # what the snapshot is named after: `_snapshot_before_upgrade` falls back to the
    # baseline for a pre-Alembic database, which records no revision at all
    named_for = before["revision"] or BASELINE_REVISION
    print(flush=True)

    backend = Backend(port)
    backend.start()
    try:
        backend.wait_until_ready()
        after = read_state(working)
        report.check(
            after["revision"] == head,
            "the migration completed and left the database at this build's head",
            f"{before['revision']} -> {after['revision']}",
        )
        compare_state(report, before, after)
        snapshot = check_snapshot_and_rotation(report, port, named_for, before["revision"])
        if snapshot:
            check_download(report, port, snapshot, scratch)
            check_restore(report, port, snapshot)
        check_import(report, port, carried)
    finally:
        backend.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="the database to take through the upgrade")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--keep", action="store_true", help="leave the throwaway data directory behind"
    )
    args = parser.parse_args()

    source = Path(args.db).expanduser().resolve()
    if not source.is_file():
        print(f"there is no database at {source}")
        return 2
    if args.port == 8000:
        print("port 8000 belongs to the running app: pick another one")
        return 2
    if not port_is_free(args.port):
        print(f"something is already listening on port {args.port}")
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="check-upgrade-"))
    # before app.config is imported, or the app resolves the user's own data
    # directory and this check writes its copies into it
    os.environ["APP_DATA_DIR"] = str(scratch)
    sys.path.insert(0, str(BACKEND))

    report = Report()
    try:
        run(source, args.port, scratch, report)
    finally:
        print(flush=True)
        if args.keep:
            print(f"data directory left at {scratch}", flush=True)
        else:
            from app import database  # noqa: PLC0415

            database.engine.dispose()
            # the app's rotating log lives in there, and Windows will not remove a
            # directory holding an open handle
            logging.shutdown()
            shutil.rmtree(scratch, ignore_errors=True)

    if report.failures:
        print(f"FAILED: {len(report.failures)} of the assertions above did not hold", flush=True)
        for label in report.failures:
            print(f"  - {label}", flush=True)
        return 1
    print("every assertion held", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
