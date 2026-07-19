# Browser-Path Refinements — Humanization & Pluggable Engines

Status: **Part 1 (humanization) and Part 2's `BrowserEngine` seam are shipped**
(`scrapers/humanize.py`, `scrapers/browser_engine.py`, `browser_humanize`
setting); the additional engines (§2.5 tasks 3–4) stay gated on Scraper Health
evidence as designed. These were the optional, non-blocking items
deferred from [plan-resilience.md](plan-resilience.md) §B.6, now that the
structural anti-bot work (transport ladder, proxy pool, health observability)
has shipped. Neither is required for the pipeline to work; both are
*incremental trust* on the browser rung of the ladder — the fallback the system
climbs to only when the free curl path is already blocked.

Two independent parts, either order:

1. **Behavioral humanization** ("ghost cursor") on the Playwright browser path —
   cheap, testable, a real (if marginal) gain against DataDome's behavioral ML.
2. **Additional browser engines** (Nodriver, SeleniumBase-CDP) behind the
   existing `browser_engine` setting — higher cost, mostly redundant with
   Camoufox, so gated on evidence.

Both must honor the browser-path invariants already in force (16/18): **fail-open**
(a humanization or engine error never fails a check — it degrades to the plain
path), **opt-in** (optional deps, never in `requirements.txt`, lazily imported),
**one dedicated Playwright thread** (the sync API is greenlet-bound), and
**unattended launches are headless**.

---

## Part 1 — Behavioral humanization on the browser path

### 1.1 Why, and why only marginal

DataDome scores a session on TLS/JA4, IP reputation, JS fingerprint **and
behavior** (mouse paths, scroll, dwell). The current browser path
(`AdProbe._browser_check_inner`) does a bare `page.goto()` + read: it produces
**zero** pointer or scroll events, which is itself a weak bot signal. Adding
human-like motion raises the behavioral component of the trust score.

Be honest about the ceiling (the 2026 research is unanimous): no single layer
bypasses DataDome, and mouse movement alone won't turn a hard block into a pass.
The value is **compounding** — on the browser rung we already bring a real
browser fingerprint (Camoufox) and, when configured, a residential proxy;
human-like behavior is the cheap third layer that makes the whole rung more
reliable. It also directly helps the **attended CAPTCHA-solve path**
(`_wait_for_human_solve`, invariant 18): moving the cursor toward the challenge
before handing off reads as human.

### 1.2 Design — a tiny internal helper, no dependency

The Python ghost-cursor ports are either stale (`python_ghost_cursor`) or drag
in a whole patched-Playwright stack (`humanization-playwright` on Patchright).
The motion itself is small — a cubic Bézier between two points with easing,
jitter, overshoot, and variable dwell — so vendor it, in the spirit of the
project already writing its own notifier on stdlib rather than pulling a library:

New module `scrapers/humanize.py`, pure geometry + thin Playwright glue:

- `bezier_path(a, b, *, steps, jitter, rng) -> list[Point]` — **pure**, the
  human-like trajectory. Fully unit-testable: endpoints honored, time
  monotone, all points within the viewport box, jitter bounded, deterministic
  under a seeded `rng`.
- `move_like_human(page, to, rng) -> None` — walks `page.mouse.move` along the
  path with easing pauses.
- `idle_browse(page, rng) -> None` — a couple of `move_like_human` hops to
  random on-screen points plus a small `page.mouse.wheel` scroll and a short
  randomized dwell. This is the one call the check makes.
- Every public function is wrapped so **any exception is swallowed** (log at
  debug): humanization is never allowed to fail a fetch (invariant 16).

### 1.3 Wiring

- In `AdProbe._browser_check_inner`, call `humanize.idle_browse(page, rng)`
  **after** `goto` and before reading `page.content()` — a real visitor lands,
  moves, glances, then the DOM is read.
- In `_wait_for_human_solve` (headful), one `move_like_human` toward the
  challenge region before the polling loop.
- Optionally in `cookie_harvester.harvest` after navigation, so a harvested
  cookie is earned by a session that also *behaved* — the cookie the curl path
  then reuses is "warmer".
- Gate with a setting `browser_humanize` (default **on** whenever the browser
  path runs; it is pure upside there and costs ~0.5–1.5 s per page, well inside
  the existing per-probe pacing). Off pins today's bare-goto behavior.

### 1.4 Tasks

1. `scrapers/humanize.py` (`bezier_path` pure + `move_like_human` /
   `idle_browse` glue, all fail-open).
2. `test_humanize.py`: `hypothesis` laws on `bezier_path` (endpoints, in-bounds,
   monotone, bounded jitter), plus a fake `page` recording `mouse.move`/`wheel`
   calls to prove `idle_browse` swallows a raising mouse and still returns.
3. Wire the three call sites; add `browser_humanize` to `config.py` (additive)
   and expose it in `SettingsModal` next to the other browser toggles.
4. Docs: note the behavioral step in invariant 16/18's browser description and
   the README's availability-check section.

### 1.5 Risk

- **Time**: bounded to ~1.5 s/page; the availability check is already paced far
  slower (invariant 16), so no new IP pressure.
- **Determinism in tests**: seed the `rng`; never call the real clock in the
  pure layer.
- **No curl-path change**: humanization is meaningless without a JS/DOM (the
  curl transport has no mouse), so it lives strictly on the browser rung.

---

## Part 2 — Additional browser engines (Nodriver / SeleniumBase-CDP)

### 2.1 The architectural reality (why this is more than "add an if")

The whole browser path is **Playwright sync API on one greenlet-bound thread**
(the `_ensure_pw_pool()` single-worker executor, invariants 16/18). Camoufox
plugs in cleanly because it *is* Playwright — `_launch_camoufox` returns a
Playwright `BrowserContext`, and `_browser_check_inner` drives it with
`ctx.new_page()`, `page.goto()`, `page.content()`, `page.mouse`.

The two candidate engines are **not** Playwright:

- **Nodriver** — asyncio-based, runs its own event loop, talks CDP directly with
  no WebDriver footprint (the 2026 research names it the strongest open-source
  option for exactly that reason).
- **SeleniumBase CDP Mode** — Selenium/WebDriver underneath, with a strategic
  disconnect/reconnect to shed the WebDriver signal; synchronous API
  (`driver.get`, `driver.get_page_source`).

Neither returns a Playwright context, so neither can be driven by the current
check/harvest code as-is. Dropping parallel per-engine copies of the check would
duplicate the block-detection and cookie-reading logic per engine — precisely
the "one fact, one implementation" trap the Conventions warn against.

### 2.2 Design — a thin `BrowserEngine` adapter seam

Define the **minimum interface** the two browser consumers actually need — the
availability probe and the cookie harvest — and program both against it:

```
class BrowserEngine(Protocol):
    def open(self, url: str) -> None: ...          # navigate
    def content(self) -> str: ...                   # visible/raw HTML for the gone/block checks
    def title(self) -> str: ...
    def cookies(self) -> list[dict]: ...            # so the harvest can persist the DataDome cookie
    def humanize(self, rng) -> None: ...            # Part 1, engine-native input API
    def close(self) -> None: ...
```

- **PlaywrightEngine** wraps today's Camoufox/Chromium context (a refactor, not a
  rewrite — the existing `_launch` becomes its `open`/`close`).
- **NodriverEngine** owns an asyncio loop *on the same single dedicated thread*
  (the sync check calls `loop.run_until_complete` on the engine's coroutines) —
  this contains the async/sync mismatch in one place instead of leaking it into
  `_browser_check_inner`.
- **SeleniumBaseEngine** is already synchronous; its adapter is thin, but the
  dep (selenium + a managed driver) is the heaviest and most redundant.

`browser_engine` extends from `auto|camoufox|chromium` to also accept
`nodriver|seleniumbase`; `is_<engine>_available()` gates each (optional dep,
lazily imported, **never** in `requirements.txt`); `auto` tries in order and
**every failure falls through to the next engine** — an unfetched Nodriver
browser must degrade to Camoufox/Chromium, never break a working check
(exactly the Camoufox contract today).

### 2.3 The cookie-sharing constraint

Whatever engine runs, the harvest must end by writing the **same** persistent
DataDome cookie into settings (`cookies()` → `datadome_cookie`), because the
curl_cffi transport — rung 0, the workhorse — reuses it. An engine that earns a
cookie it can't export buys nothing for the free path. The adapter's `cookies()`
is therefore non-optional.

### 2.4 Verdict — build the seam, add engines on evidence

Camoufox already delivers the bulk of the self-hosted benefit the research
reports (top open-source sustained rate), so a second stealth engine is
**diversification, not a new capability**, at real cost (an async loop to
marshal, a WebDriver footprint to manage, +150–300 MB optional browsers). The
disciplined move:

1. **Do Part 1 first** (behavioral gain, cheap, no dep).
2. **Extract the `BrowserEngine` seam** by refactoring Camoufox/Chromium behind
   it — no new dependency, purely internal, and it makes a future engine a
   drop-in.
3. **Add Nodriver only if the data says so.** We now *have* the data:
   `scraper_health`'s per-portal block-rate (plan-resilience B.5) is the trigger
   — if Camoufox's block rate stays low, a second engine is dead weight. Let the
   panel, not a guess, justify the integration cost.
4. **SeleniumBase-CDP last**, if ever — heaviest dep, most overlap with the
   Playwright/Nodriver paths.

### 2.5 Tasks (staged)

1. `scrapers/browser_engine.py`: the Protocol + `PlaywrightEngine` refactor of
   the current `_launch`/context handling; `_browser_check_inner` and the
   harvest reprogrammed against the interface. Behavior identical on
   Camoufox/Chromium — existing browser-path behavior is the regression baseline.
2. Extend `browser_engine` settings validation + `SettingsModal` options; extend
   `AdProbe.browser_status`/`transport` diagnostics to name the engine.
3. `NodriverEngine` (optional dep, gated, fail-open to the seam's next choice) —
   **only when** `scraper_health` shows a Camoufox block-rate that warrants it.
4. `SeleniumBaseEngine` — optional, lowest priority.
5. Tests: a `FakeEngine` proves the probe/harvest logic is engine-agnostic
   (block detection, cookie export, fail-open on `open()` raising). Real engine
   launches stay in the documented untestable-network bucket, like today's
   Camoufox path.

### 2.6 Risk & invariant notes

- **Fail-open preserved end to end**: an engine that won't launch degrades to
  the next, and ultimately to Chromium/curl — never a crash, never a wrong
  "gone" (invariant 16).
- **Single PW thread respected**: the Nodriver loop lives on that same thread;
  no second greenlet context is introduced.
- **Opt-in / offline**: new engines are optional deps gated by
  `is_*_available()`; a Pi with none installed behaves exactly as now.
- **No requirements.txt growth**: like Playwright and Camoufox, these stay out
  of the product deps.

---

## Suggested sequence

1. **Part 1 ghost-cursor** — cheap, testable, immediate behavioral gain on the
   rung that needs it. Do this regardless.
2. **Part 2 `BrowserEngine` seam** — internal refactor, no new dep, unlocks
   drop-in engines and better diagnostics.
3. **Nodriver adapter** — only if `scraper_health` block-rate justifies it.
4. **SeleniumBase-CDP** — optional, last.

The theme is the same as the resilience plan: prefer the cheap, measured
improvement, and let the health panel — not intuition — decide when the
expensive diversification is worth its integration cost.

---

## Sources

- [The Web Scraping Club — Bypass DataDome: mouse movements in Playwright with Ghost Cursor](https://substack.thewebscraping.club/p/bypass-datadome-mouse-movements-in-playwright)
- [The Web Scraping Club — Oxymouse and Playwright for human-like mouse movements](https://substack.thewebscraping.club/p/oxymouse-and-playwright-mouse-movements)
- [DKprofile/ghost-cursor-playwright — human-like mouse movements for Playwright](https://github.com/DKprofile/ghost-cursor-playwright/)
- [humanization-playwright (PyPI) — Bézier paths, variable delays on Patchright](https://pypi.org/project/humanization-playwright/)
- [Scrapfly — How to Bypass DataDome (engines: Nodriver, SeleniumBase-CDP, Camoufox)](https://scrapfly.io/blog/posts/how-to-bypass-datadome-anti-scraping)
- [ZenRows — Bypass DataDome, Complete Guide 2026](https://www.zenrows.com/blog/datadome-bypass)
