"""`python -m app.livecheck` — run a search through every transport separately.

Three ways to say what to check: URLs on the command line, `--profiles` for the
saved searches the app actually monitors, or `--replay DIR` to re-run the
parsers over an earlier run's captures without touching the network.

Everything that costs something is off by default. The browser rung has to be
asked for by name (invariant 18), the paid rung needs `--paid`, and the credit
cap and account floor apply on top of that — the defaults are the budget, and
raising one is a deliberate act with a number attached.
"""

import argparse
import sys
from pathlib import Path

from ..config import load_settings
from .budget import (
    DEFAULT_CREDIT_FLOOR,
    DEFAULT_MAX_CREDITS,
    DEFAULT_MAX_REQUESTS,
    Budget,
)
from .report import render, succeeded
from .rungs import active_profiles, replay, run_checks


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.livecheck",
        description=(
            "Ask one search through every transport separately and report, per "
            "rung, what the portal answered and what the parsers made of it."
        ),
    )
    p.add_argument("urls", nargs="*", help="search URLs to check")
    p.add_argument(
        "--profiles",
        action="store_true",
        help="check every active saved search instead (the database is opened read-only)",
    )
    p.add_argument(
        "--replay",
        metavar="DIR",
        help="re-parse a previous run's captures; makes no network call at all",
    )
    p.add_argument(
        "--rungs",
        metavar="NAMES",
        help=(
            "comma-separated rungs to try: a family (curl, api) or an exact name "
            "(curl:safari184, curl+cookie, browser, official). "
            "Default: everything except browser."
        ),
    )
    p.add_argument("--paid", action="store_true", help="allow the paid scrape-API rung")
    p.add_argument(
        "--max-credits",
        type=int,
        default=DEFAULT_MAX_CREDITS,
        help=f"credits the paid rung may spend in this run (default {DEFAULT_MAX_CREDITS})",
    )
    p.add_argument(
        "--credit-floor",
        type=int,
        default=DEFAULT_CREDIT_FLOOR,
        help=(
            f"refuse the paid rung below this account balance (default {DEFAULT_CREDIT_FLOOR}; "
            "0 also allows a provider that reports no balance)"
        ),
    )
    p.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_MAX_REQUESTS,
        help=f"requests per portal from this connection (default {DEFAULT_MAX_REQUESTS})",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=None,
        help="seconds between requests to one portal (default: the app's request_delay_seconds)",
    )
    p.add_argument("--out", metavar="DIR", help="where to write the run directory")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.replay:
        run = replay(Path(args.replay))
        print(render(run))
        return 0 if succeeded(run) else 1

    urls = list(args.urls)
    if args.profiles:
        urls += active_profiles()
    if not urls:
        print("nothing to check: pass a search URL, --profiles, or --replay DIR", file=sys.stderr)
        return 2

    settings = load_settings()
    budget = Budget(
        max_requests=args.max_requests,
        delay_seconds=(
            args.delay
            if args.delay is not None
            else float(settings.get("request_delay_seconds", 6))
        ),
        max_credits=args.max_credits,
        credit_floor=args.credit_floor,
        paid=args.paid,
    )
    rung_filter = [r.strip() for r in args.rungs.split(",") if r.strip()] if args.rungs else None

    run = run_checks(
        urls,
        budget=budget,
        rung_filter=rung_filter,
        out_root=Path(args.out) if args.out else None,
        settings=settings,
    )
    print(render(run))
    print(f"\nwritten to {run.directory}")
    return 0 if succeeded(run) else 1


if __name__ == "__main__":
    raise SystemExit(main())
