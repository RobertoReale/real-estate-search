"""Does a search actually work from this machine, and through which transport?

Nothing else in this repository talks to a portal, so nothing else can answer
that question: the gates can prove the parsers still parse and the scheduler
still schedules while every real scan comes back "blocked". This package is the
instrument that closes the gap. It runs one search through every rung of the
transport ladder *separately* — each impersonation on its own, the saved cookie
on its own, the browser on its own, the paid provider on its own — and reports,
per rung, what the portal answered and what the real parsers made of it.

It is a diagnostic and never a scan: it writes nothing into the database, it
sends no notification, and it is bounded by `budget.Budget` rather than by
persistence, because it runs from the connection the owner's scans go out from
and a matrix of transports is exactly the retry loop invariant 8 forbids.

`docs/live-checks.md` is the manual; `python -m app.livecheck --help` is the
short version.
"""

from .budget import Budget
from .report import Attempt, Run, verdicts, write_report
from .rungs import run_checks, run_rungs

__all__ = [
    "Attempt",
    "Budget",
    "Run",
    "run_checks",
    "run_rungs",
    "verdicts",
    "write_report",
]
