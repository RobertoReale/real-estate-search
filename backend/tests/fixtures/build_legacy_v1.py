r"""Rebuilds `legacy_v1.db`: a database as release 1.0.0 wrote it.

`test_upgrade_path.py` opens that file with the current code and counts what is
still in it afterwards. The file is committed rather than built at test time for
the reason the test exists at all: a fixture generated from today's models is
today's schema wearing an old name, and it proves nothing about the schema anyone
actually installed.

Which makes this script the fixture's documentation. It says exactly what is in
the file, and it is how the file is rebuilt if it ever has to be:

    cd backend && .venv\Scripts\python tests/fixtures/build_legacy_v1.py

Two halves, both frozen on purpose:

- **The schema** is `LEGACY_SCHEMA`, taken verbatim from a database built by
  release 1.0.0's own models (`git show v1.0.0:backend/app/models.py`), down to
  the Alembic revision that release left recorded. It is a constant rather than
  something regenerated, so this script still produces a 1.0.0 database in a
  year's time, when the current models have moved on again.
- **The contents** are the demo corpus (`app/services/demo_data.py`), so there is
  no second generator here and nothing in the file is real — plus the few fields
  only a person produces: notes, and a property marked sold. A scan-shaped corpus
  has no reason to contain those, and they are exactly what an upgrade that
  rewrites a table loses with nothing failing.

Everything is pinned — the corpus seed, its size, and `now` — so a rebuild
differs from the committed file only where this script was deliberately changed.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
FIXTURE = HERE / "legacy_v1.db"

# What release 1.0.0's `upgrade head` left in `alembic_version`. Frozen with the
# schema below: it is a fact about that release, not about the current head.
LEGACY_REVISION = "0002_drop_imports"

# The corpus, pinned. 24 properties is enough for several of every case the
# generator draws (gone, hidden, merged across two portals, price history,
# favourite, tagged, no photo, no pin) and small enough to keep the committed
# file in the tens of kilobytes.
COUNT = 24
NOW = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)

# The user's own work, which no scan writes. Indexes into the corpus in id order.
NOTES = {
    2: "Vista dal balcone ottima, ma il palazzo non ha ascensore. Ripassare di sera.",
    9: "L'agenzia dice che il prezzo è trattabile: partire da 15k sotto la richiesta.",
    17: "Riscaldamento centralizzato e spese condominiali alte. Chiedere l'ultimo bilancio.",
}
SOLD_AFTER = 5  # the first still-active property from here on is marked sold

# The schema, verbatim from release 1.0.0. `alembic_version` is Alembic's own
# table and is not built by create_all, so it is written out here beside the rest.
LEGACY_SCHEMA = """
CREATE TABLE commute_cache (
	id INTEGER NOT NULL,
	leg VARCHAR NOT NULL,
	distance_m FLOAT,
	duration_s FLOAT,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE geocode_cache (
	id INTEGER NOT NULL,
	"query" VARCHAR NOT NULL,
	latitude FLOAT,
	longitude FLOAT,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE listing_profiles (
	listing_id INTEGER NOT NULL,
	profile_id INTEGER NOT NULL,
	first_seen_at DATETIME NOT NULL,
	PRIMARY KEY (listing_id, profile_id),
	FOREIGN KEY(listing_id) REFERENCES listings (id),
	FOREIGN KEY(profile_id) REFERENCES search_profiles (id)
);
CREATE TABLE listings (
	id INTEGER NOT NULL,
	property_id INTEGER NOT NULL,
	portal VARCHAR NOT NULL,
	portal_id VARCHAR NOT NULL,
	url VARCHAR NOT NULL,
	price FLOAT,
	agency VARCHAR NOT NULL,
	description TEXT NOT NULL,
	image_url VARCHAR NOT NULL,
	first_seen_at DATETIME NOT NULL,
	last_seen_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(property_id) REFERENCES properties (id)
);
CREATE TABLE price_history (
	id INTEGER NOT NULL,
	property_id INTEGER NOT NULL,
	old_price FLOAT,
	new_price FLOAT NOT NULL,
	changed_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(property_id) REFERENCES properties (id)
);
CREATE TABLE pricing_snapshots (
	id INTEGER NOT NULL,
	captured_on DATE NOT NULL,
	city VARCHAR NOT NULL,
	zone VARCHAR NOT NULL,
	contract VARCHAR NOT NULL,
	median_sqm_price FLOAT NOT NULL,
	sample_count INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE properties (
	id INTEGER NOT NULL,
	fingerprint VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	city VARCHAR NOT NULL,
	zone VARCHAR NOT NULL,
	address VARCHAR NOT NULL,
	latitude FLOAT,
	longitude FLOAT,
	rooms INTEGER,
	floor VARCHAR NOT NULL,
	sqm FLOAT,
	contract VARCHAR NOT NULL,
	current_min_price FLOAT,
	first_price FLOAT,
	image_url VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	filtered_reason VARCHAR NOT NULL,
	source VARCHAR NOT NULL,
	is_favorite BOOLEAN NOT NULL,
	notes TEXT NOT NULL,
	first_seen_at DATETIME NOT NULL,
	last_seen_at DATETIME NOT NULL,
	gone_at DATETIME,
	sold_at DATETIME,
	PRIMARY KEY (id)
);
CREATE TABLE property_audits (
	id INTEGER NOT NULL,
	property_id INTEGER NOT NULL,
	text_digest VARCHAR NOT NULL,
	model VARCHAR NOT NULL,
	payload TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(property_id) REFERENCES properties (id)
);
CREATE TABLE property_tags (
	property_id INTEGER NOT NULL,
	tag_id INTEGER NOT NULL,
	PRIMARY KEY (property_id, tag_id),
	FOREIGN KEY(property_id) REFERENCES properties (id),
	FOREIGN KEY(tag_id) REFERENCES tags (id)
);
CREATE TABLE scraper_health_snapshots (
	id INTEGER NOT NULL,
	captured_on DATE NOT NULL,
	portal VARCHAR NOT NULL,
	attempts INTEGER NOT NULL,
	successes INTEGER NOT NULL,
	blocked INTEGER NOT NULL,
	errors INTEGER NOT NULL,
	last_transport VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE search_profiles (
	id INTEGER NOT NULL,
	name VARCHAR NOT NULL,
	portal VARCHAR NOT NULL,
	search_url VARCHAR NOT NULL,
	excluded_keywords TEXT NOT NULL,
	notify_channels VARCHAR NOT NULL,
	is_active BOOLEAN NOT NULL,
	last_run_at DATETIME,
	last_run_status VARCHAR NOT NULL,
	last_run_detail VARCHAR NOT NULL,
	consecutive_failures INTEGER NOT NULL,
	baseline_done BOOLEAN NOT NULL,
	health_alert_sent BOOLEAN NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE tags (
	id INTEGER NOT NULL,
	name VARCHAR NOT NULL,
	name_normalized VARCHAR NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL,
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE UNIQUE INDEX ix_commute_cache_leg ON commute_cache (leg);
CREATE UNIQUE INDEX ix_geocode_cache_query ON geocode_cache ("query");
CREATE INDEX ix_listing_profiles_profile_id ON listing_profiles (profile_id);
CREATE INDEX ix_listings_portal ON listings (portal);
CREATE INDEX ix_listings_portal_id ON listings (portal_id);
CREATE INDEX ix_listings_property_id ON listings (property_id);
CREATE INDEX ix_price_history_property_id ON price_history (property_id);
CREATE INDEX ix_pricing_snapshots_captured_on ON pricing_snapshots (captured_on);
CREATE INDEX ix_pricing_snapshots_city ON pricing_snapshots (city);
CREATE INDEX ix_properties_city ON properties (city);
CREATE INDEX ix_properties_contract ON properties (contract);
CREATE INDEX ix_properties_fingerprint ON properties (fingerprint);
CREATE INDEX ix_properties_source ON properties (source);
CREATE UNIQUE INDEX ix_property_audits_property_id ON property_audits (property_id);
CREATE INDEX ix_scraper_health_snapshots_captured_on ON scraper_health_snapshots (captured_on);
CREATE INDEX ix_scraper_health_snapshots_portal ON scraper_health_snapshots (portal);
CREATE UNIQUE INDEX ix_tags_name_normalized ON tags (name_normalized);
"""

# Parents before children. SQLite does not enforce foreign keys unless asked to,
# but a fixture whose rows arrived in an order no application could produce is
# one nobody can reason about.
COPY_ORDER = (
    "search_profiles",
    "tags",
    "properties",
    "listings",
    "listing_profiles",
    "price_history",
    "property_tags",
)


def _seed_scratch(path: Path) -> None:
    """Write the corpus, at the current schema, into a throwaway database.

    The generator goes through the ORM (that is the whole point of it), so it can
    only write the schema the models describe — today's. The legacy file is filled
    from this one, column by column, in `_copy_into_legacy`.
    """
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.database import Base
    from app.models import Property
    from app.services import demo_data

    engine = create_engine(f"sqlite:///{path}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            demo_data.seed_demo(db, count=COUNT, now=NOW)
            properties = list(db.scalars(select(Property).order_by(Property.id)))
            for index, note in NOTES.items():
                properties[index].notes = note
            sold = next(p for p in properties[SOLD_AFTER:] if p.status == "active")
            sold.status = "sold"
            sold.sold_at = NOW - timedelta(days=9)
            db.commit()
    finally:
        engine.dispose()


def _copy_into_legacy(conn: sqlite3.Connection, scratch: Path) -> None:
    """Move every row across, restricted to the columns 1.0.0 had.

    Reading the column list off the legacy database rather than the scratch one
    is what performs the downgrade: a column the models grew since simply has
    nowhere to land.
    """
    conn.execute("ATTACH DATABASE ? AS scratch", (str(scratch),))
    try:
        for table in COPY_ORDER:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            names = ", ".join(f'"{c}"' for c in columns)
            conn.execute(f"INSERT INTO {table} ({names}) SELECT {names} FROM scratch.{table}")
        conn.commit()
    finally:
        conn.execute("DETACH DATABASE scratch")


def build(target: Path) -> dict[str, int]:
    """(Re)write the fixture at `target`, returning its row counts."""
    target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as workshop:
        scratch = Path(workshop) / "current.db"
        _seed_scratch(scratch)

        conn = sqlite3.connect(target)
        conn.isolation_level = None  # VACUUM cannot run inside a transaction
        try:
            # WAL because that is the mode the application leaves its database
            # in (`database._sqlite_pragmas`), and the fixture is meant to be the
            # file an installed release wrote, not an approximation of it. The
            # -wal and -shm companions are folded back in on a clean close, so
            # what stays on disk is the single file this returns.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(LEGACY_SCHEMA)
            conn.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (LEGACY_REVISION,))
            _copy_into_legacy(conn, scratch)
            conn.execute("VACUUM")
            return {
                table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for table in COPY_ORDER
            }
        finally:
            conn.close()


def main() -> int:
    # Ahead of the first `app` import: `app.config` resolves the data directory
    # once, at import time, and creates it. A script that only ever writes to
    # tests/fixtures/ has no business touching the developer's own.
    os.environ["APP_DATA_DIR"] = str(Path(tempfile.gettempdir()) / "legacy-v1-build")
    sys.path.insert(0, str(BACKEND))

    counts = build(FIXTURE)
    for name, count in counts.items():
        print(f"{count:6}  {name}")
    print(f"\n{FIXTURE} ({FIXTURE.stat().st_size / 1024:.0f} KB), at {LEGACY_REVISION}")
    leftovers = [
        p.name
        for p in (FIXTURE.with_name(FIXTURE.name + s) for s in ("-wal", "-shm"))
        if p.exists()
    ]
    if leftovers:
        print(f"[ERROR] not folded back into the fixture: {', '.join(leftovers)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
