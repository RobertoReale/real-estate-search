"""Laws for the ghost-cursor module (scrapers/humanize.py).

The pure trajectory (`bezier_path`) gets hypothesis laws: whatever endpoints
and seed you feed it, the path must honor the endpoints, stay inside the
viewport box, keep jitter bounded, and be deterministic under a seeded rng —
these are the guarantees the glue relies on to never send the mouse outside
the window (which Playwright would reject, and a swallowed rejection would
silently disable the whole behavioral layer).

The glue (`move_like_human` / `idle_browse`) is tested against a fake page:
it must actually produce pointer/scroll events, and — invariant 16 — a mouse
that raises must be swallowed, never propagated into the check.
"""

import random

from hypothesis import given
from hypothesis import strategies as st

from app import config
from app.scrapers import humanize

_coord = st.floats(min_value=0.0, max_value=1500.0, allow_nan=False, allow_infinity=False)
_seed = st.integers(min_value=0, max_value=2**32 - 1)
_steps = st.integers(min_value=2, max_value=60)
_jitter = st.floats(min_value=0.0, max_value=10.0, allow_nan=False)

BOUNDS = (1600.0, 1600.0)


@given(_coord, _coord, _coord, _coord, _steps, _seed)
def test_path_length_and_endpoints(ax, ay, bx, by, steps, seed):
    path = humanize.bezier_path(
        (ax, ay), (bx, by), steps=steps, bounds=BOUNDS, rng=random.Random(seed)
    )
    assert len(path) == steps + 1
    # Endpoints are exact — jitter and the curve's bow never touch them.
    assert path[0] == (ax, ay)
    assert path[-1] == (bx, by)


@given(_coord, _coord, _coord, _coord, _seed)
def test_path_stays_in_bounds(ax, ay, bx, by, seed):
    # The bow and the overshoot control point can push the raw curve outside
    # the box; the clamp must catch every point, or Playwright refuses the move.
    path = humanize.bezier_path((ax, ay), (bx, by), bounds=(800.0, 600.0), rng=random.Random(seed))
    for p in path:
        assert 0.0 <= p.x <= 800.0
        assert 0.0 <= p.y <= 600.0


@given(_coord, _coord, _coord, _coord, _seed)
def test_path_deterministic_under_seed(ax, ay, bx, by, seed):
    p1 = humanize.bezier_path((ax, ay), (bx, by), bounds=BOUNDS, rng=random.Random(seed))
    p2 = humanize.bezier_path((ax, ay), (bx, by), bounds=BOUNDS, rng=random.Random(seed))
    assert p1 == p2


@given(_coord, _coord, _coord, _coord, _seed, _jitter)
def test_jitter_bounded(ax, ay, bx, by, seed, jitter):
    # Same seed → same control points (the jitter draws happen after them and
    # are consumed either way), so the jittered path may deviate from the
    # jitter-free one by at most `jitter` per axis. Clamping only shrinks the
    # difference.
    base = humanize.bezier_path(
        (ax, ay), (bx, by), jitter=0.0, bounds=BOUNDS, rng=random.Random(seed)
    )
    wobbly = humanize.bezier_path(
        (ax, ay), (bx, by), jitter=jitter, bounds=BOUNDS, rng=random.Random(seed)
    )
    eps = 1e-9
    for p0, p1 in zip(base, wobbly, strict=True):
        assert abs(p1.x - p0.x) <= jitter + eps
        assert abs(p1.y - p0.y) <= jitter + eps


# ---------------------------------------------------------------- glue layer


class FakeMouse:
    def __init__(self):
        self.moves: list[tuple[float, float]] = []
        self.wheels: list[tuple[float, float]] = []

    def move(self, x, y):
        self.moves.append((x, y))

    def wheel(self, dx, dy):
        self.wheels.append((dx, dy))


class FakePage:
    viewport_size = {"width": 1000, "height": 700}

    def __init__(self, mouse=None):
        self.mouse = mouse or FakeMouse()
        self.waits: list[float] = []

    def wait_for_timeout(self, ms):
        self.waits.append(ms)


class RaisingMouse(FakeMouse):
    def move(self, x, y):
        raise RuntimeError("greenlet exploded")

    def wheel(self, dx, dy):
        raise RuntimeError("greenlet exploded")


def test_idle_browse_produces_events_inside_viewport():
    page = FakePage()
    humanize.idle_browse(page, rng=random.Random(42))
    assert page.mouse.moves, "no pointer events — the behavioral layer did nothing"
    assert page.mouse.wheels, "no scroll event"
    for x, y in page.mouse.moves:
        assert 0.0 <= x <= 1000.0
        assert 0.0 <= y <= 700.0


def test_move_like_human_chains_from_last_position():
    page = FakePage()
    humanize.move_like_human(page, (500.0, 300.0), rng=random.Random(1))
    first_run_end = page.mouse.moves[-1]
    assert first_run_end == (500.0, 300.0)
    n = len(page.mouse.moves)
    humanize.move_like_human(page, (100.0, 100.0), rng=random.Random(2))
    # The second hop starts where the first ended, not at a random corner.
    assert page.mouse.moves[n] == first_run_end


def test_raising_mouse_is_swallowed():
    # Invariant 16: humanization must never fail a fetch. A mouse that raises
    # on every call still lets idle_browse return normally.
    page = FakePage(mouse=RaisingMouse())
    assert humanize.idle_browse(page, rng=random.Random(7)) is None
    assert humanize.move_like_human(page, (10.0, 10.0), rng=random.Random(7)) is None


def test_setting_off_means_no_events():
    config.save_settings({"browser_humanize": False})
    page = FakePage()
    humanize.idle_browse(page, rng=random.Random(3))
    humanize.move_like_human(page, (50.0, 50.0), rng=random.Random(3))
    assert page.mouse.moves == []
    assert page.mouse.wheels == []
    assert page.waits == []


def test_setting_defaults_on():
    # Default-on: the browser rung is opt-in already, and behavior there is
    # pure upside; the setting exists to pin the old bare-goto path if needed.
    assert config.load_settings().get("browser_humanize") is True
    page = FakePage()
    humanize.idle_browse(page, rng=random.Random(5))
    assert page.mouse.moves
