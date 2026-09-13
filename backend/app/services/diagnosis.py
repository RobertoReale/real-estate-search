"""The "try this search" diagnosis: the live-check harness, run for one
monitored search and answered in terms the dashboard can show.

Everything that talks to a portal is `app.livecheck` and stays there — this
module chooses which rungs that harness may climb, how much the attempt is
allowed to cost, and how often it may be asked for at all. What comes back is
the harness's own table with one translation applied: every reason becomes a
**code**, never a sentence. The browser renders the sentence, in the language the
owner reads, from the same dictionary as the rest of the UI; a message composed
here would exist in one language and bypass it.

Three limits, each for a different reason:

- **Ten minutes per search.** The harness is polite by construction, but a button
  is not: a diagnosis is a handful of requests from the owner's residential
  address, and a button that can be pressed twice in a row is the retry loop
  invariant 8 forbids, wearing a mouse. The cooldown is taken *before* the run
  starts, so it doubles as the in-flight guard — a second press while the first
  run is still climbing is refused by the same check.
- **The browser rung only when a browser is already opted into** (invariant 18):
  a diagnosis must never be the thing that launches a browser on a machine whose
  owner chose not to have one.
- **The paid rung only when asked for explicitly, and only inside the month's
  credit ceiling** (the one `transport_policy` refuses scans against). The
  ceiling is read from the same ledger the scans spend from, and a paid
  diagnosis writes its receipt back to it — a diagnosis that spent credits
  outside the ledger would leave the ceiling looking untouched, which is the
  failure that ledger exists to prevent.
"""

import logging
import time

from sqlalchemy.orm import Session

from ..config import load_settings
from ..livecheck.budget import CREDITS_PER_PAGE, Budget
from ..livecheck.report import Attempt, Run, pages, redact
from ..livecheck.rungs import run_checks, secrets_of
from ..models import SearchProfile
from ..scrapers import transport_policy
from . import scraper_health

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 600

# One diagnosis is one page per rung, and there are at most six free rungs plus
# the geography lookup. Below the harness's own default, because this runs from
# a click rather than from an operator who chose the moment.
MAX_REQUESTS = 8

# The settings that mean "a browser is wanted here". Any one of them is consent
# (invariant 18); none of them means the browser rung is never even built.
BROWSER_SETTINGS = (
    "datadome_auto_refresh",
    "availability_browser_first",
    "availability_browser_headful",
)

# The free ladder, named explicitly because naming any rung replaces the
# harness's default selection — which excludes the browser and would otherwise
# take the decision above out of our hands. `api` is listed so the paid rung
# always produces a row: "not requested" is a fact the table has to state, and a
# rung that is absent reads as one that does not exist.
FREE_RUNGS = ("curl", "curl+cookie", "api", "official")

# When the run was last allowed to start, per search. Process-local and not
# persisted: it guards this process's residential connection, and a restart is
# rare enough that re-arming it costs one extra diagnosis.
_last_at: dict[int, float] = {}


def cooldown_left(profile_id: int, now: float | None = None) -> int:
    """Seconds before this search may be diagnosed again. 0 when it may now."""
    started = _last_at.get(profile_id)
    if started is None:
        return 0
    elapsed = (time.monotonic() if now is None else now) - started
    return max(0, int(round(COOLDOWN_SECONDS - elapsed)))


def forget_cooldowns() -> None:
    """Drop every cooldown. For the tests, which must not inherit each other's."""
    _last_at.clear()


# --- what the run is allowed to cost ------------------------------------


def browser_enabled(settings: dict) -> bool:
    return any(bool(settings.get(key)) for key in BROWSER_SETTINGS)


def rung_filter(settings: dict) -> list[str]:
    """The rungs this diagnosis may climb, as `--rungs` would name them."""
    wanted: list[str] = list(FREE_RUNGS)
    if browser_enabled(settings):
        wanted.append("browser")
    return wanted


def paid_allowance(db: Session, settings: dict) -> int:
    """Credits this diagnosis may spend before the month's ceiling refuses it.

    Zero means the ceiling is reached (or too close to pay for one page), and
    the paid rung must not be asked for at all — the same answer
    `transport_policy` gives a scan, read from the same ledger.
    """
    spent = scraper_health.credits_this_month(db)["spent"]
    if transport_policy.budget_spent(spent, settings):
        return 0
    ceiling = transport_policy.monthly_credit_budget(settings)
    if ceiling <= 0:
        return CREDITS_PER_PAGE
    return CREDITS_PER_PAGE if ceiling - spent >= CREDITS_PER_PAGE else 0


# --- the harness's answer, as codes -------------------------------------

# A skip reason is a sentence the harness wrote for an operator reading a
# terminal. Matched on the fragment that identifies it rather than on the whole
# string, so a reason that gains a clause keeps its code; anything unrecognised
# falls through to `skipped`, which the UI renders as the sentence itself.
_SKIP_CODES = (
    ("datadome_cookie", "no_cookie"),
    ("no browser is installed", "no_browser"),
    ("the browser rung was not opened", "no_browser"),
    ("no scrape-API provider", "no_api_key"),
    ("no Idealista API key", "no_official_key"),
    ("needs --paid", "paid_not_requested"),
    ("blocked attempts in a row", "streak"),
    ("request cap reached", "request_cap"),
    ("credit cap reached", "credit_cap"),
    ("below the floor", "credit_floor"),
    ("did not report its remaining credits", "credit_unknown"),
    ("the official API has no parameter", "unsupported_search"),
    ("the official API needs a centroid", "unsupported_search"),
)


def skip_code(reason: str) -> str:
    for fragment, code in _SKIP_CODES:
        if fragment in reason:
            return code
    return "skipped"


def _row(attempt: Attempt, secrets: list[str], *, paid_refused: str = "") -> dict:
    """One rung's line of the table: what it is, whether it worked, and why."""
    outcome = attempt.outcome
    if outcome == "skipped":
        reason = paid_refused if paid_refused and attempt.rung.startswith("api") else ""
        reason = reason or skip_code(attempt.skipped)
    else:
        reason = outcome
    return {
        "rung": attempt.rung,
        "target": attempt.target,
        "portal": attempt.portal,
        "outcome": outcome,
        "reason": reason,
        "status": attempt.status,
        "listings": attempt.listings,
        "credits": attempt.credits,
        "elapsed_ms": attempt.elapsed_ms,
        # The harness redacts as it measures; redacted again here because this
        # is a boundary a secret must not cross, and only the free text can
        # carry one. Shown by the UI only where no code explains the row.
        "detail": redact(attempt.skipped or attempt.error, secrets),
    }


def _advice(attempts: list[Attempt]) -> tuple[str, str]:
    """What the whole run means, as a code, and the rung that earned it.

    Read off the attempts that actually asked for a page: resolving Immobiliare's
    geography is a request and is reported as one, but it succeeds against an
    endpoint anti-bot rarely guards, and a run where every transport was refused
    must not be able to announce that the search works.
    """
    asked = [a for a in pages(attempts) if not a.skipped]
    if not asked:
        return "nothing_tried", ""
    if winner := next((a for a in asked if a.outcome == "ok"), None):
        return "works", winner.rung
    if winner := next((a for a in asked if a.outcome == "no_results"), None):
        return "no_results", winner.rung
    if all(a.outcome == "blocked" for a in asked):
        return "blocked", ""
    return "error", ""


def _record_spending(db: Session, portal: str, run: Run) -> None:
    """Put a paid diagnosis's receipt in the ledger the ceiling is read from.

    The outcome and the transport are left empty: this row books money, not a
    scan, so the two columns that describe a scan are not the diagnosis's to
    write — `count_attempt=False` means neither is read.
    """
    if not run.credits_spent:
        return
    paid = [a for a in run.attempts if a.rung.startswith("api:") and not a.skipped]
    scraper_health.record_scan(
        db,
        portal,
        "",
        "",
        credits=run.credits_spent,
        credits_estimated=sum(1 for a in paid if a.credits is None) * CREDITS_PER_PAGE,
        api_calls=len(paid),
        count_attempt=False,
    )
    db.commit()


def diagnose(db: Session, profile: SearchProfile, *, paid: bool = False) -> dict:
    """Climb the ladder for one search and report every rung.

    Synchronous on purpose: the route is a plain `def`, so FastAPI runs it in the
    threadpool and the rest of the API — progress above all — keeps answering
    while this waits out the harness's polite spacing.
    """
    settings = load_settings()
    secrets = secrets_of(settings)
    allowance = paid_allowance(db, settings) if paid else 0
    paid_refused = "budget" if paid and not allowance else ""

    _last_at[profile.id] = time.monotonic()
    budget = Budget(
        max_requests=MAX_REQUESTS,
        delay_seconds=float(settings.get("request_delay_seconds") or 6.0),
        max_credits=allowance or CREDITS_PER_PAGE,
        paid=bool(allowance),
    )
    run = run_checks(
        [profile.search_url],
        budget=budget,
        rung_filter=rung_filter(settings),
        settings=settings,
        labels=[profile.name],
    )
    rows = [_row(a, secrets, paid_refused=paid_refused) for a in run.attempts]
    advice, winner = _advice(run.attempts)
    try:
        _record_spending(db, profile.portal, run)
    except Exception:  # pragma: no cover - the ledger must never fail a diagnosis
        logger.exception("recording the diagnosis spending failed")
    return {
        "profile_id": profile.id,
        "name": profile.name,
        "portal": profile.portal,
        "ran_at": run.started_at,
        "advice": advice,
        "winner": winner,
        "paid": bool(allowance),
        "credits_spent": run.credits_spent,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "rungs": rows,
    }
