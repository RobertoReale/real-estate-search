"""`python -m app.livecheck` — run a search through every transport separately.

Four ways to say what to check: URLs on the command line, `--profiles` for the
saved searches the app actually monitors, `--suite` for the tracked reference
searches that cover every shape a search can have, or `--replay DIR` to re-run
the parsers over an earlier run's captures without touching the network.

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
from .suite import (
    every_search_answered,
    render_comparison,
    render_suite,
    request_cap,
    run_suite,
    suite_complaints,
)


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
        "--suite",
        action="store_true",
        help=(
            "check the tracked reference searches instead: one per shape a search "
            "can have, climbing one rung each and stopping at the first that parses"
        ),
    )
    p.add_argument(
        "--all-rungs",
        action="store_true",
        help="with --suite: try every rung against every search, not just the first that parses",
    )
    p.add_argument(
        "--compare-form",
        action="store_true",
        help=(
            "implies --suite: also print the pasted and form-built totals side by "
            "side, with what the restatement approximated or dropped"
        ),
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
        default=None,
        help=(
            f"requests per portal from this connection (default {DEFAULT_MAX_REQUESTS}; "
            "--suite scales it to the number of searches)"
        ),
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
    suite = args.suite or args.compare_form

    if args.replay:
        run = replay(Path(args.replay))
        print(render(run))
        return 0 if succeeded(run) else 1

    urls = list(args.urls)
    if args.profiles:
        urls += active_profiles()
    if suite and urls:
        # Refused rather than merged: the suite's request cap is sized for the
        # suite, and quietly checking someone's saved searches under it would
        # cut one list or the other short without saying which.
        print("--suite checks its own list: drop the URLs and --profiles", file=sys.stderr)
        return 2
    if not suite and not urls:
        print(
            "nothing to check: pass a search URL, --profiles, --suite, or --replay DIR",
            file=sys.stderr,
        )
        return 2
    if suite and (complaints := suite_complaints()):
        # The list has stopped describing the shapes it claims to, so nothing it
        # measured would mean what the table says. Caught before a request.
        print("\n".join(["the reference suite is not sound:", *complaints]), file=sys.stderr)
        return 2

    settings = load_settings()
    max_requests = args.max_requests
    if max_requests is None:
        max_requests = request_cap() if suite else DEFAULT_MAX_REQUESTS
    budget = Budget(
        max_requests=max_requests,
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
    out_root = Path(args.out) if args.out else None

    if suite:
        run = run_suite(
            budget=budget,
            rung_filter=rung_filter,
            out_root=out_root,
            settings=settings,
            all_rungs=args.all_rungs,
        )
        print(render(run))
        print(f"\n{render_suite(run)}")
        if args.compare_form:
            print(f"\n{render_comparison(run)}")
        print(f"\nwritten to {run.directory}")
        return 0 if every_search_answered(run) else 1

    run = run_checks(
        urls,
        budget=budget,
        rung_filter=rung_filter,
        out_root=out_root,
        settings=settings,
    )
    print(render(run))
    print(f"\nwritten to {run.directory}")
    return 0 if succeeded(run) else 1


if __name__ == "__main__":
    raise SystemExit(main())
