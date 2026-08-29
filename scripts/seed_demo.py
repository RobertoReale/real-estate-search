"""Fills an empty database with the demo corpus.

The corpus itself, and the reasoning behind its shape, live in
`backend/app/services/demo_data.py`. This is the way to run it from outside the
application: point it at a throwaway data directory and it produces a dashboard
worth looking at — eighty properties, three monitored searches — without a scan,
a portal or a network connection.

    python scripts/seed_demo.py --data-dir .demo-data

`--data-dir` becomes `APP_DATA_DIR`, which is what decides where `case.db` and
`settings.json` are read and written (see `backend/app/config.py`). Omitted, the
usual data directory is used and named on stdout before anything is written.

It refuses a database that already holds properties, searches or tags, and exits
non-zero when it does: the corpus is invented data, and invented data mixed into
real listings cannot be separated again.
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a database with the demo corpus.")
    parser.add_argument(
        "--data-dir",
        help="where case.db and settings.json live; created if missing "
        "(default: the application's usual data directory)",
    )
    parser.add_argument(
        "--count",
        type=int,
        help="how many properties to generate (default: the corpus size)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="the generator's seed; the same seed always produces the same corpus",
    )
    args = parser.parse_args(argv)

    if args.data_dir:
        os.environ["APP_DATA_DIR"] = str(Path(args.data_dir).expanduser().resolve())
    sys.path.insert(0, str(ROOT / "backend"))

    # Imported here, below the environment variable: `config` resolves the data
    # directory once, at import time, so an import at the top of this file would
    # have opened the wrong database before --data-dir was ever read.
    from app.config import DB_PATH
    from app.database import SessionLocal, init_db
    from app.services import demo_data

    print(f"Database: {DB_PATH}")
    init_db()

    options = {k: v for k, v in (("count", args.count), ("seed", args.seed)) if v is not None}
    with SessionLocal() as db:
        try:
            summary = demo_data.seed_demo(db, **options)
        except demo_data.DatabaseNotEmpty as exc:
            print(f"[ERROR] {exc}")
            return 1

    print(
        f"Seeded {summary.properties} properties, {summary.listings} listings, "
        f"{summary.price_changes} price changes, {summary.tags} tags "
        f"and {summary.profiles} monitored searches."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
