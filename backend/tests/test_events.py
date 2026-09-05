"""The one stream the dashboard keeps open, and the three promises it makes.

The stream replaced four browser timers, so what has to hold is: it says
something when something changed, it says *nothing* when nothing did (or the
timers come back as a firehose), and it never holds a database session for the
life of a connection (or a handful of open tabs exhausts the SQLite pool with no
scan running at all).

Invariant 14's half of it lives in `test_api_auth.py`, which drives the
middleware `/api/events` sits behind like every other `/api` route. The case
asserted here is the one specific to this route: it is registered under `/api`,
so it inherits that gate rather than sidestepping it.
"""

import asyncio
import json

from app.database import SessionLocal, init_db
from app.main import app
from app.models import Property, SearchProfile
from app.services import events


def _frames(text: str) -> list[tuple[str, dict]]:
    """The (topic, payload) pairs in a run of SSE frames, heartbeats dropped."""
    out = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if line and not line.startswith(":")]
        if not lines:
            continue
        topic = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        out.append((topic, json.loads(data)))
    return out


async def _take(hub: events.EventHub, count: int, timeout: float = 5.0) -> list[str]:
    """The first `count` frames one subscriber receives, then disconnect."""
    chunks: list[str] = []
    stream = hub.subscribe()

    async def pump():
        async for chunk in stream:
            chunks.append(chunk)
            if len(chunks) >= count:
                return

    try:
        await asyncio.wait_for(pump(), timeout)
    except TimeoutError:
        pass
    finally:
        await stream.aclose()
    return chunks


# --------------------------------------------------------------------------
# the frames themselves
# --------------------------------------------------------------------------


def test_a_new_subscriber_is_handed_the_whole_world_first():
    """A reconnection has to be a resynchronisation.

    The backend restarting, or standby dropping the socket, must not leave a
    dashboard showing the state it had when the stream broke — and it must not
    have to ask for anything to catch up either, or the polling this replaced
    is simply back under a different name.
    """
    init_db()
    frames = _frames("".join(asyncio.run(_take(events.EventHub(), 4))))
    assert {topic for topic, _ in frames} == {"status", "availability", "geocode", "health"}


def test_an_idle_stream_says_nothing_but_the_heartbeat():
    """The whole point: silence costs nothing.

    With no scan, no batch and no database change, the sampler must publish
    exactly once — the opening snapshot — and then hold its tongue. A topic
    republished every tick would be the 800 ms poll again, over a socket.
    """
    init_db()
    hub = events.EventHub()

    async def listen():
        # Four opening frames, then whatever arrives over several ticks.
        return await _take(hub, 5, timeout=events.TICK_SECONDS * 4)

    chunks = asyncio.run(listen())
    extra = _frames("".join(chunks[4:]))
    assert extra == [], f"an unchanged topic was republished: {extra}"


def test_a_changed_property_set_moves_the_fingerprint():
    """The grid's trigger. Everything the dashboard re-reads hangs off this."""
    init_db()
    with SessionLocal() as db:
        before = events.properties_version(db)
        db.add(Property(fingerprint="fp1", city="Milano", status="active"))
        db.commit()
        after = events.properties_version(db)
    assert before != after


def test_hiding_a_property_moves_the_fingerprint():
    """`count(*)` would not move here, and the row leaves the grid all the same.

    This is why the fingerprint groups by status instead of counting rows: a
    dashboard in a second tab has to learn that a property it is showing has
    just been hidden in the first.
    """
    init_db()
    with SessionLocal() as db:
        prop = Property(fingerprint="fp1", city="Milano", status="active")
        db.add(prop)
        db.commit()
        before = events.properties_version(db)
        prop.status = "hidden"
        db.commit()
        assert events.properties_version(db) != before


def test_a_blocked_scan_moves_the_health_fingerprint():
    """The transition nothing else can see.

    A scan that gets blocked writes no property, so the property fingerprint
    sits exactly where it was. Without this second one the health panel would
    keep reading "ok" until something unrelated happened to change.
    """
    init_db()
    with SessionLocal() as db:
        profile = SearchProfile(
            name="Milano", portal="immobiliare", search_url="https://www.immobiliare.it/x"
        )
        db.add(profile)
        db.commit()
        before = events.health_version(db)
        profile.last_run_status = "blocked"
        profile.consecutive_failures = 3
        db.commit()
        assert events.health_version(db) != before


def test_a_scan_starting_is_published():
    init_db()
    hub = events.EventHub()

    async def listen():
        stream = hub.subscribe()
        chunks: list[str] = []

        async def pump():
            async for chunk in stream:
                chunks.append(chunk)

        task = asyncio.create_task(pump())
        # Let the opening snapshot land, then change the world underneath it.
        await asyncio.sleep(events.TICK_SECONDS * 0.5)
        opened = len(chunks)
        from app.services.scanner import scan_state

        scan_state["running"] = True
        try:
            await asyncio.sleep(events.TICK_SECONDS * 2.5)
        finally:
            scan_state["running"] = False
            task.cancel()
            # The generator is only closable once nothing is iterating it.
            await asyncio.gather(task, return_exceptions=True)
            await stream.aclose()
        return chunks[opened:]

    published = _frames("".join(asyncio.run(listen())))
    assert any(topic == "status" and payload["running"] for topic, payload in published)


# --------------------------------------------------------------------------
# what it must not do
# --------------------------------------------------------------------------


def test_a_sample_never_leaves_a_session_open():
    """The "Careful" of this task, asserted rather than promised.

    A session held for the life of a connection pins a pooled SQLite connection
    for as long as a tab stays open. On the default pool that is a handful of
    idle dashboards and nothing left for a scan.
    """
    init_db()
    opened: list[object] = []
    closed: list[object] = []
    real = events.SessionLocal

    def spy():
        session = real()
        opened.append(session)
        original_close = session.close

        def close():
            closed.append(session)
            original_close()

        session.close = close  # pyright: ignore[reportAttributeAccessIssue]
        return session

    events.SessionLocal = spy  # pyright: ignore[reportAttributeAccessIssue]
    try:
        events.collect_snapshot()
    finally:
        events.SessionLocal = real  # pyright: ignore[reportAttributeAccessIssue]
    assert opened and opened == closed


def test_the_sampler_stops_when_the_last_subscriber_leaves():
    """Nobody watching, nothing sampled. A ticker that outlives its audience is
    a database query per second on an idle machine, forever."""
    init_db()
    hub = events.EventHub()

    async def connect_and_go():
        await _take(hub, 4)
        # The sampler notices at its next wake, not instantly.
        await asyncio.sleep(events.TICK_SECONDS * 2)
        return hub._sampler

    assert asyncio.run(connect_and_go()) is None


def test_a_client_that_stops_reading_is_resynchronised_not_replayed():
    """A slow reader must not be able to grow the process's memory, and must not
    end up permanently stale either. Every frame is a whole snapshot, so the
    recovery is the current one rather than the backlog."""
    hub = events.EventHub()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2)
    hub._queues.add(queue)
    for i in range(10):
        hub.publish("status", {"tick": i})
    assert queue.qsize() <= 2
    last = None
    while not queue.empty():
        last = queue.get_nowait()
    assert last is not None
    assert _frames(last)[0][1] == {"tick": 9}


# --------------------------------------------------------------------------
# the route
# --------------------------------------------------------------------------


def test_the_stream_is_an_api_route_and_a_get():
    """Invariant 14, on this route specifically: outbound-only over the existing
    origin, under `/api` so the optional token gate in `main.py` covers it, and
    nothing anywhere that registers a callback address."""
    paths = app.openapi()["paths"]
    assert list(paths["/api/events"]) == ["get"]
    assert "text/event-stream" in paths["/api/events"]["get"]["responses"]["200"]["content"]
