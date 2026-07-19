"""Human-like pointer behavior for the browser rung ("ghost cursor").

Why this exists: DataDome scores a session on TLS, IP reputation, JS
fingerprint AND behavior. The browser path used to do a bare `goto()` + read,
producing zero pointer or scroll events — itself a weak bot signal. A few
Bézier-curved mouse hops and a small scroll raise the behavioral component of
the trust score. No single layer beats DataDome; this is the cheap third layer
on a rung that already brings a real fingerprint (Camoufox) and, when
configured, a residential proxy.

Vendored rather than depended on: the Python ghost-cursor ports are either
stale or drag in a patched-Playwright stack, and the motion itself is a cubic
Bézier with easing, jitter and overshoot — the same "stdlib over a library"
call as the notifier.

Two layers, deliberately separated:

  * `bezier_path` is PURE geometry (deterministic under a seeded rng), so the
    trajectory laws are unit-testable without a browser.
  * `move_like_human` / `idle_browse` are thin Playwright glue. Every public
    glue function SWALLOWS every exception (logged at debug): humanization is
    never allowed to fail a fetch (invariant 16), and it no-ops entirely when
    the `browser_humanize` setting is off.

This lives strictly on the browser rung: the curl transport has no mouse, so
there is nothing to humanize there.
"""

from __future__ import annotations

import functools
import logging
import math
import random
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

# Fallback when the page cannot report a viewport (Camoufox launches with
# no_viewport=True, so `page.viewport_size` is often None there).
DEFAULT_VIEWPORT = (1280.0, 720.0)

# Module-level rng for production calls; tests pass their own seeded one.
_rng = random.Random()


class Point(NamedTuple):
    x: float
    y: float


def _ease(t: float) -> float:
    """Smoothstep: slow start, fast middle, slow arrival — a hand, not a servo."""
    return t * t * (3.0 - 2.0 * t)


def bezier_path(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    steps: int = 24,
    jitter: float = 2.0,
    bounds: tuple[float, float] | None = None,
    rng: random.Random | None = None,
) -> list[Point]:
    """Cubic Bézier trajectory from `a` to `b` with easing, jitter and a hint
    of overshoot. Pure: same rng state → same path.

    Guarantees (the laws test_humanize.py holds it to):
      * exactly `steps + 1` points;
      * first == `a` and last == `b` (clamped into `bounds` when given) —
        jitter never touches the endpoints;
      * every point inside `bounds` ([0, w] × [0, h]) when given;
      * each intermediate point within `jitter` per axis of the jitter-free
        curve drawn from the same rng state.
    """
    rng = rng or _rng
    steps = max(int(steps), 2)
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    dist = math.hypot(dx, dy)
    # Perpendicular unit vector: the curve bows sideways off the straight line.
    if dist > 0:
        px, py = -dy / dist, dx / dist
    else:
        px = py = 0.0
    bow1 = rng.uniform(-0.25, 0.25) * dist
    bow2 = rng.uniform(-0.25, 0.25) * dist
    t1 = rng.uniform(0.2, 0.45)
    # The second control point may sit slightly PAST the target (t > 1): the
    # hand overshoots and settles back, which the curve reproduces naturally.
    t2 = rng.uniform(0.7, 1.08)
    c1x, c1y = ax + dx * t1 + px * bow1, ay + dy * t1 + py * bow1
    c2x, c2y = ax + dx * t2 + px * bow2, ay + dy * t2 + py * bow2

    def clamp(x: float, y: float) -> Point:
        if bounds is not None:
            x = min(max(x, 0.0), float(bounds[0]))
            y = min(max(y, 0.0), float(bounds[1]))
        return Point(x, y)

    points: list[Point] = []
    for i in range(steps + 1):
        t = _ease(i / steps)
        u = 1.0 - t
        x = u * u * u * ax + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * bx
        y = u * u * u * ay + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * by
        # Jitter is drawn even when it lands on an endpoint, so the rng stream
        # (and thus the base curve) is identical across jitter settings.
        jx = rng.uniform(-jitter, jitter)
        jy = rng.uniform(-jitter, jitter)
        if 0 < i < steps:
            x += jx
            y += jy
        points.append(clamp(x, y))
    return points


def enabled() -> bool:
    """Whether the `browser_humanize` setting allows behavioral input.
    Defaults ON — on the browser rung it is pure upside — and, in the fail-open
    spirit, an unreadable settings file also means on."""
    try:
        from ..config import load_settings

        return bool(load_settings().get("browser_humanize", True))
    except Exception:
        return True


def _failopen(fn):
    """Humanization must never fail a check: any exception out of the glue is
    swallowed (invariant 16) and only whispered at debug level."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.debug("humanize: %s swallowed %s: %s", fn.__name__, type(e).__name__, e)
            return None

    return wrapper


def _viewport(page: Any) -> tuple[float, float]:
    try:
        vs = page.viewport_size
        if vs and vs.get("width") and vs.get("height"):
            return float(vs["width"]), float(vs["height"])
    except Exception:
        pass
    return DEFAULT_VIEWPORT


@_failopen
def move_like_human(
    page: Any,
    to: tuple[float, float] | None = None,
    rng: random.Random | None = None,
) -> None:
    """Walk `page.mouse.move` along a Bézier path with easing pauses.

    `to=None` targets a point near the viewport center — where a DataDome
    challenge widget sits, which is what the headful solve path wants. The
    cursor's last position is remembered on the page object so consecutive
    hops chain instead of teleporting back to a corner.
    """
    if not enabled():
        return
    rng = rng or _rng
    w, h = _viewport(page)
    if to is None:
        to = (w * rng.uniform(0.4, 0.6), h * rng.uniform(0.35, 0.55))
    start = getattr(page, "_humanize_pos", None)
    if start is None:
        # A fresh page: pretend the cursor arrives from somewhere plausible.
        start = (w * rng.uniform(0.2, 0.8), h * rng.uniform(0.2, 0.8))
    path = bezier_path(start, to, steps=rng.randint(18, 30), jitter=2.5, bounds=(w, h), rng=rng)
    for i, p in enumerate(path):
        page.mouse.move(p.x, p.y)
        # A few micro-pauses along the way; every step would cost seconds.
        if i % 6 == 5:
            page.wait_for_timeout(rng.uniform(15, 45))
    try:
        page._humanize_pos = (path[-1].x, path[-1].y)
    except Exception:
        pass


@_failopen
def idle_browse(page: Any, rng: random.Random | None = None) -> None:
    """A real visitor lands, moves, glances, scrolls a little — then the DOM is
    read. One call per page, budgeted at ~0.5–1.5 s, well inside the probe's
    per-ad pacing (invariant 16)."""
    if not enabled():
        return
    rng = rng or _rng
    w, h = _viewport(page)
    for _ in range(rng.randint(1, 2)):
        target = (w * rng.uniform(0.15, 0.85), h * rng.uniform(0.2, 0.8))
        move_like_human(page, target, rng=rng)
    try:
        page.mouse.wheel(0, rng.randint(150, 600))
    except Exception:
        pass
    page.wait_for_timeout(rng.uniform(200, 600))
