"""One outbound stream carrying everything the dashboard used to ask for on a timer.

Four things change under the dashboard without anyone clicking: the property set
(a scan lands, a second tab hides a row), the scan's own progress, the
availability batch's, and the geocoding batch's. Each of them had its own timer
in the browser — 800 ms for the two batches, 4 s during a scan and 30 s
otherwise for the grid — which meant a dashboard sitting open on a phone all day
made thousands of requests to be told nothing had happened, and a browser that
had two tabs open made twice as many.

What replaces them is this module and `routers/events.py`: **one sampler for the
whole process**, publishing to every connected browser at once. The shape is
deliberately a sampler rather than a set of hooks in the producers:

* the producers are threads. `scan_state`, `_scan_progress`, the two batch
  progress dicts — all of them are module-level dicts written from a worker
  thread and copied out on read, which is the existing design and a good one.
  Reaching into an event loop from those threads to publish would put an
  `asyncio` handoff into the middle of a scan; reading their snapshots from here
  costs them nothing and cannot break them.
* the fingerprint has no producer at all. `properties_version` is a property of
  the database, moved by a scan, by the user hiding a row, and by a second tab
  doing either. Nothing in the code is in a position to announce it; the only
  honest way to know is to look.

So the total cost of knowing is **one tick per second, for the whole machine,
and only while at least one browser is connected** — against one HTTP request
per timer per tab before. The sampler stops when the last subscriber leaves.

Nothing here holds a database session open: each tick opens one, reads two small
aggregates, and closes it. A session held for the life of an SSE connection
would pin a SQLite connection from the pool for as long as a tab stayed open,
which on the four-connection default is four idle tabs and no scan.

Invariant 14 is untouched. This is a `GET` on the existing origin that the
browser opens and the server writes to: no inbound port, no webhook, no
callback address. It is behind the same `require_api_token` middleware as every
other `/api` route, which is why the client reads it with `fetch` and an
`Authorization` header rather than with `EventSource` — `EventSource` cannot
send one.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import SessionLocal
from ..models import PriceHistory, Property, SearchProfile

logger = logging.getLogger(__name__)

# How often the sampler looks. One second is the resolution of the fastest thing
# it reports (the batch progress bars, which used to poll at 800 ms) and is well
# under the cadence of the slowest (a scan page, seconds apart at best).
TICK_SECONDS = 1.0

# A line down an idle connection, so a client that has silently lost the server
# — standby, a dropped Wi-Fi, a proxy that reaps quiet sockets — finds out
# rather than sitting on a stream that will never speak again.
HEARTBEAT_SECONDS = 10.0

# Frames a client may fall behind by before it is resynchronised wholesale.
# Every frame is a complete snapshot of its topic, so the recovery is simply to
# send the current one rather than to replay what was missed.
_QUEUE_LIMIT = 32


def frame(topic: str, payload: Any) -> str:
    """One Server-Sent Events frame: a named event and its JSON body."""
    return f"event: {topic}\ndata: {json.dumps(payload, default=str)}\n\n"


def properties_version(db: Session) -> str:
    """A cheap fingerprint of the property set: "did anything change?".

    The dashboard used to answer that question by re-downloading every filtered
    property — market position, match score, deal score and provenance computed
    for each — every 30 seconds, and every 4 seconds during a scan. Now the
    sampler above reads this string once for the whole machine and the grid is
    re-read only when it moves.

    Two small aggregates. The per-status counts are what make it trustworthy: a
    new property raises one, and every lifecycle transition — a scan marking
    rows `gone`, the user hiding one or marking it `sold` — moves a row from one
    bucket to another, which the grid must reflect because those rows enter or
    leave it. Grouping rather than a single total is the difference: hiding a
    property leaves `count(*)` exactly where it was. `max(last_seen_at)` catches
    a scan that re-found existing listings and changed nothing else, and the
    newest price-history id catches a price change on a property already shown.

    Not a perfect change detector, and it does not try to be: editing notes or
    toggling a favourite moves none of these. Those are user actions, and the
    client that performs one already refreshes on the response.
    """
    rows = db.execute(
        select(
            Property.status,
            func.count(Property.id),
            func.max(Property.id),
            func.max(Property.last_seen_at),
        ).group_by(Property.status)
    ).all()
    last_price = db.execute(select(func.max(PriceHistory.id))).scalar()
    buckets = ";".join(
        f"{status}:{count}:{max_id}:{last_seen}"
        for status, count, max_id, last_seen in sorted(rows, key=lambda r: r[0] or "")
    )
    return f"{buckets}|{last_price}"


def health_version(db: Session) -> str:
    """A fingerprint of the scraping health, for the same reason as above.

    A blocked scan is the one that changes nothing else: it writes no property,
    so `properties_version` sits exactly where it was and the health panel would
    have kept showing "ok" until something unrelated moved. The outcome and the
    failure streak are the two columns the panel and the profile rows read, so
    those are what is watched.
    """
    rows = db.execute(
        select(
            SearchProfile.id,
            SearchProfile.last_run_status,
            SearchProfile.consecutive_failures,
            SearchProfile.last_run_at,
        ).order_by(SearchProfile.id)
    ).all()
    return ";".join(f"{pid}:{status}:{streak}:{ran}" for pid, status, streak, ran in rows)


def collect_snapshot() -> dict[str, Any]:
    """Everything the stream reports, as it stands right now.

    Serialised through the same response models as the REST routes that used to
    be polled, so a client receives byte-identical shapes whichever way it
    learns. A payload hand-assembled here would drift from the schema the
    generated types are built from, and the drift would surface as an
    `undefined` in the browser rather than as a failing gate.

    Synchronous on purpose: the caller runs it in a worker thread, because the
    two queries below are SQLite reads and blocking the event loop on them would
    stall every other connection the process is serving.
    """
    from ..config import load_settings
    from . import scheduler
    from .availability_check import get_prop_check_progress
    from .geocoder import get_geocode_progress
    from .scanner import get_scan_progress, scan_state

    with SessionLocal() as db:
        data_version = properties_version(db)
        health = health_version(db)

    status = schemas.ScraperStatusOut(
        **scan_state,
        next_auto_run=scheduler.next_run_time(),
        paused=bool(load_settings().get("scanning_paused")),
        data_version=data_version,
        progress=schemas.ScanProgressOut(**get_scan_progress()),
    )
    return {
        "status": status.model_dump(mode="json"),
        "availability": schemas.AvailabilityCheckProgressOut(
            **get_prop_check_progress()
        ).model_dump(mode="json"),
        "geocode": schemas.GeocodeProgressOut(**get_geocode_progress()).model_dump(mode="json"),
        "health": {"version": health},
    }


class EventHub:
    """The subscribers, the last snapshot of each topic, and the sampler.

    One instance per process (`hub`, below). It publishes a topic only when its
    payload differs from the last one sent, which is what makes a second of
    resolution affordable: an idle dashboard receives a heartbeat every ten
    seconds and nothing else.
    """

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[str]] = set()
        self._latest: dict[str, Any] = {}
        self._sampler: asyncio.Task[None] | None = None

    # -- publishing -------------------------------------------------------

    def publish(self, topic: str, payload: Any) -> None:
        """Send a topic to every subscriber, if it has actually moved."""
        if self._latest.get(topic) == payload:
            return
        self._latest[topic] = payload
        text = frame(topic, payload)
        for queue in list(self._queues):
            if queue.full():
                # This client is not reading fast enough. Replaying the backlog
                # would only make it further behind, and every frame is a whole
                # snapshot anyway, so drop what is queued and hand it the world
                # as it stands.
                self._resync(queue)
                continue
            queue.put_nowait(text)

    def _resync(self, queue: asyncio.Queue[str]) -> None:
        while not queue.empty():
            queue.get_nowait()
        for topic, payload in self._latest.items():
            if queue.full():
                return
            queue.put_nowait(frame(topic, payload))

    async def _sample(self) -> None:
        snapshot = await asyncio.to_thread(collect_snapshot)
        for topic, payload in snapshot.items():
            self.publish(topic, payload)

    async def _run(self) -> None:
        """Sample for as long as somebody is listening, then stop."""
        try:
            while self._queues:
                try:
                    await self._sample()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # A sampler that dies takes every connected dashboard's
                    # updates with it, silently. One bad tick is not worth that.
                    logger.exception("event sampler tick failed")
                await asyncio.sleep(TICK_SECONDS)
        finally:
            self._sampler = None

    def _ensure_sampler(self) -> None:
        if self._sampler is None or self._sampler.done():
            self._sampler = asyncio.create_task(self._run())

    # -- subscribing ------------------------------------------------------

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """One connection's worth of frames, until the client goes away.

        The current state of every topic is sent first, which is what makes a
        reconnection a resynchronisation: a browser that lost the stream while
        the backend restarted is fully up to date on the first frame of the new
        one, without asking for anything.
        """
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=_QUEUE_LIMIT)
        self._queues.add(queue)
        try:
            if not self._latest:
                # First subscriber of this process: sample now rather than make
                # it wait a tick to learn anything at all.
                await self._sample()
            self._ensure_sampler()
            # Anything that sample just queued is already in the snapshot below,
            # and sending both would open every connection with each topic
            # twice — which for a dashboard is a duplicate invalidation and for
            # a test is an idle stream that looks anything but.
            while not queue.empty():
                queue.get_nowait()
            for topic, payload in list(self._latest.items()):
                yield frame(topic, payload)
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            self._queues.discard(queue)

    # -- shutdown ---------------------------------------------------------

    async def aclose(self) -> None:
        """Stop the sampler. Called when the application shuts down."""
        task = self._sampler
        self._queues.clear()
        self._sampler = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


hub = EventHub()
