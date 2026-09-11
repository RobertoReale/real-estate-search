"""What a live check writes down: one row per attempt, the verdict a person
reads, and the on-disk record that makes `--replay` possible.

Two rules govern everything here.

**No secret is ever written.** The provider key travels in the query string of
every paid request, so every URL is redacted before it reaches the table, the
JSON or a log line, and cookies are not recorded at all — not their value, not a
preview of it. Redaction happens twice on purpose: once where an attempt is
built, and again at the write, because the test that matters is the one asserting
the key is absent from `report.json`.

**Every number is measured.** A column is left empty where the attempt did not
produce it, never filled with a plausible zero. `declared_total` is the case that
earns the rule: `None` means the portal published no total, which is a different
fact from a total of nothing (invariant 26), and a rung that reports a count
without a page behind it is exactly the failure this instrument exists to catch.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Below this length a "secret" is more likely to be a common word than a
# credential, and blanking it out of every message would make the report
# unreadable. Every key these providers issue is far longer.
_MIN_SECRET_LENGTH = 8

# Query parameters that carry a credential on the transports this tool drives:
# Scrapfly's `key`, ScraperAPI's `api_key`, and the bearer forms an error
# message may quote back. Matched over whole strings rather than parsed URLs so
# a URL quoted inside an exception text is redacted too, and held to the same
# length floor so a sort order (`key=asc`) still reads as one.
_SECRET_QUERY_RE = re.compile(
    r"(?i)\b(key|api[-_]?key|token|access[-_]?token)=([^&\s\"'<>]{"
    + str(_MIN_SECRET_LENGTH)
    + ",})"
)

OK_OUTCOMES = ("ok", "no_results")


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """`text` with every credential removed: known secret values by literal
    match, and anything shaped like `key=...` by pattern."""
    if not text:
        return text
    out = _SECRET_QUERY_RE.sub(r"\1=***", text)
    for secret in secrets:
        if secret and len(secret) >= _MIN_SECRET_LENGTH:
            out = out.replace(secret, "***")
    return out


@dataclass
class Attempt:
    """One rung asked one target for one page, and what came back.

    An attempt that never left is recorded too, with `skipped` holding the
    budget's reason: a run that stopped early must say so in the same table as
    the requests it did make, or the absence reads as a pass.
    """

    portal: str
    rung: str
    target: str
    # which parser the body belongs to: api-next | html | official | prepare.
    # Recorded rather than inferred from `target`, because `--replay` has only
    # this file to work from and guessing a parser from a label is how a replay
    # quietly stops reproducing the run it claims to reproduce.
    kind: str = "html"
    url: str = ""
    status: int | None = None
    bytes: int = 0
    elapsed_ms: int = 0
    # block signals, kept apart from the verdict they feed: a 200 carrying
    # DataDome's wall and a bare 403 are the same outcome and not the same event
    block_marker: bool = False
    captcha: bool = False
    refused_status: bool = False
    # what the real parsers made of the body
    listings: int = 0
    strategy: str = ""
    declared_total: int | None = None
    no_results: bool = False
    samples: list[dict] = field(default_factory=list)
    credits: int | None = None
    error: str = ""
    capture: str = ""
    skipped: str = ""
    # A step that is not a page fetch — resolving geography — has nothing to
    # parse, so it states its own success instead of having one inferred from a
    # listing count it could never produce.
    resolved: bool = False
    # What the official-API parser needs and the payload does not carry. Kept on
    # the attempt so `--replay` can re-parse that capture like any other.
    contract: str = ""
    city: str = ""
    # Which named search this attempt belongs to, when the run checked several
    # at once. Empty for a single URL, where the column would say nothing.
    search: str = ""

    @property
    def blocked(self) -> bool:
        return self.refused_status or self.block_marker or self.captcha

    @property
    def outcome(self) -> str:
        """The four-word verdict `ScrapeResult.outcome` uses, in its order:
        listings parsed win, then a block, then an error, and `no_results` only
        where the portal proved it."""
        if self.skipped:
            return "skipped"
        if self.listings or self.resolved:
            return "ok"
        if self.blocked:
            return "blocked"
        if self.no_results:
            return "no_results"
        return "error"


@dataclass
class Run:
    """Everything one invocation measured."""

    started_at: str
    network: str  # "live" | "replay"
    targets: list[str]
    budget: dict
    attempts: list[Attempt] = field(default_factory=list)
    credits_spent: int = 0
    directory: str = ""

    @property
    def portals(self) -> list[str]:
        """Portals in the order they were first checked."""
        seen: list[str] = []
        for attempt in self.attempts:
            if attempt.portal not in seen:
                seen.append(attempt.portal)
        return seen


def redact_attempt(attempt: Attempt, secrets: Iterable[str] = ()) -> Attempt:
    """A copy of `attempt` with nothing quotable left in it."""
    secrets = list(secrets)
    clean = Attempt(**asdict(attempt))
    clean.url = redact(attempt.url, secrets)
    clean.error = redact(attempt.error, secrets)
    clean.skipped = redact(attempt.skipped, secrets)
    clean.samples = [
        {**sample, "title": redact(str(sample.get("title", "")), secrets)}
        for sample in attempt.samples
    ]
    return clean


# --- the table ----------------------------------------------------------

_HEADERS = (
    "PORTAL",
    "RUNG",
    "TARGET",
    "HTTP",
    "BYTES",
    "MS",
    "OUTCOME",
    "ADS",
    "STRATEGY",
    "DECLARED",
    "CREDITS",
    "NOTE",
)
_NOTE_WIDTH = 64


def _row(attempt: Attempt) -> list[str]:
    note = attempt.skipped or attempt.error
    if len(note) > _NOTE_WIDTH:
        note = note[: _NOTE_WIDTH - 1] + "…"
    return [
        attempt.portal,
        attempt.rung,
        attempt.target,
        "" if attempt.status is None else str(attempt.status),
        f"{attempt.bytes:,}" if attempt.bytes else "",
        str(attempt.elapsed_ms) if attempt.elapsed_ms else "",
        attempt.outcome,
        str(attempt.listings) if attempt.listings else "",
        attempt.strategy,
        "" if attempt.declared_total is None else f"{attempt.declared_total:,}",
        "" if attempt.credits is None else str(attempt.credits),
        note,
    ]


def render_table(attempts: list[Attempt]) -> str:
    """The run as a plain-text table, one line per attempt.

    A run that checked several named searches gets a `SEARCH` column in front;
    one that checked a single URL does not, because every row would repeat the
    same word.
    """
    labelled = any(a.search for a in attempts)
    headers = (("SEARCH",) if labelled else ()) + _HEADERS
    rows = [list(headers)] + [([a.search] if labelled else []) + _row(a) for a in attempts]
    widths = [max(len(row[i]) for row in rows) for i in range(len(headers))]
    return "\n".join(
        "  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)).rstrip()
        for row in rows
    )


# --- the verdict --------------------------------------------------------


def _credits_note(attempt: Attempt) -> str:
    return f", {attempt.credits} credits" if attempt.credits else ""


def pages(attempts: Iterable[Attempt]) -> list[Attempt]:
    """The attempts that actually asked a portal for a page.

    Resolving Immobiliare's geography is a request and is reported as one, but it
    is a step *towards* a rung rather than a rung, and it succeeds against a
    lookup endpoint that anti-bot rarely touches. The first live run made the
    case for this filter: every transport was refused with a 403 and the run
    still announced "works via prepare (geography)". A setup step must never be
    able to answer the question the tool exists to ask.
    """
    return [a for a in attempts if a.kind != "prepare"]


def _free_summary(attempts: list[Attempt]) -> str:
    """What the rungs that leave from this machine had to say, in one clause."""
    direct = [a for a in pages(attempts) if a.rung.split(":", 1)[0] not in ("api", "official")]
    tried = [a for a in direct if not a.skipped]
    if not tried:
        return "no free rung was tried"
    blocked = [a for a in tried if a.outcome == "blocked"]
    if len(blocked) == len(tried):
        statuses = sorted({str(a.status) for a in blocked if a.status is not None})
        how = f" ({', '.join(statuses)})" if statuses else ""
        dropped = any("blocked attempts in a row" in a.skipped for a in direct if a.skipped)
        tail = "; the rest were not tried" if dropped else ""
        plural = (
            "every free rung tried was refused"
            if len(tried) > 1
            else "the free rung tried was refused"
        )
        return f"{plural}{how}{tail}"
    working = [a for a in tried if a.outcome in OK_OUTCOMES]
    if working:
        return f"{len(working)} of {len(tried)} free attempts got through"
    return f"no free rung got through ({len(tried)} attempts)"


def verdicts(run: Run) -> dict[str, str]:
    """One sentence per portal, in the words a person would use."""
    out: dict[str, str] = {}
    for portal in run.portals:
        attempts = [a for a in run.attempts if a.portal == portal]
        winner = next((a for a in pages(attempts) if a.outcome in OK_OUTCOMES), None)
        if winner:
            what = "works" if winner.outcome == "ok" else "answers (nothing matches this search)"
            head = f"{portal}: {what} via {winner.rung} ({winner.target}{_credits_note(winner)})"
        else:
            head = f"{portal}: no rung worked"
        out[portal] = f"{head}; {_free_summary(attempts)}"
    return out


def succeeded(run: Run) -> bool:
    """True when every portal checked had at least one rung that parsed listings
    or proved the search matched nothing. This is the exit code."""
    if not run.portals:
        return False
    return all(
        any(a.outcome in OK_OUTCOMES for a in pages(run.attempts) if a.portal == portal)
        for portal in run.portals
    )


def render(run: Run) -> str:
    """The whole run as the tool prints it: table, then one verdict per portal."""
    lines = [render_table(run.attempts), ""]
    lines += list(verdicts(run).values())
    if run.credits_spent:
        lines.append(f"credits spent: {run.credits_spent}")
    return "\n".join(lines)


# --- the record on disk -------------------------------------------------


def new_run_directory(root: Path) -> Path:
    """`root/<timestamp>/`, created. Local time, because the person reading it
    is the one whose clock the scan ran on."""
    directory = root / datetime.now().strftime("%Y%m%d-%H%M%S")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def capture_name(attempt: Attempt, suffix: str) -> str:
    """A file name for a captured body: readable, and unique per attempt.

    The search name leads it when there is one: several searches of the same
    shape climb the same rungs, and without it the second one's capture would
    overwrite the first and `--replay` would report one page twice.
    """
    stem = "-".join(p for p in (attempt.search, attempt.portal, attempt.rung, attempt.target) if p)
    return re.sub(r"[^a-z0-9.+-]+", "_", stem.lower()) + suffix


def write_report(directory: Path, run: Run, secrets: Iterable[str] = ()) -> Path:
    """Write `report.json` and return its path. Redacts again on the way out:
    this is the boundary the secret must not cross."""
    secrets = list(secrets)
    clean = [redact_attempt(a, secrets) for a in run.attempts]
    payload = {
        "started_at": run.started_at,
        "network": run.network,
        "targets": [redact(t, secrets) for t in run.targets],
        "budget": run.budget,
        "credits_spent": run.credits_spent,
        "verdicts": verdicts(Run(**{**asdict(run), "attempts": clean})),
        "attempts": [{**asdict(a), "outcome": a.outcome} for a in clean],
    }
    path = directory / "report.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_report(directory: Path) -> dict:
    """The `report.json` of an earlier run, for `--replay`."""
    return json.loads((directory / "report.json").read_text(encoding="utf-8"))
