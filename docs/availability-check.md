# Is This Ad Still Online?

[← Back to README](../README.md)

Listings stay in your dashboard until a scan stops finding them, and a scan
only marks a property *gone* after a week of absence. When you want to know
right now — before calling an agent, or before building a shortlist — select
the properties you care about and press **Check online availability**. The app
opens each ad page once and marks the removed ones, which you can then hide in
one go.

If the portal refuses to answer (a block, a timeout, a server error), the
listing is left exactly as it was. Silence never counts as proof: a live ad
wrongly reported as gone invites you to throw it away, which costs far more
than a dead ad you click once. Listings the dashboard has seen recently are
resolved from the local database without contacting the portal at all, and
already-checked ones are skipped when checking in bulk — re-select a single
property to force a fresh check.

## Why it is deliberately slow

The check visits the portal's homepage first (as a browser would), then one ad
page every 6–8 seconds, at most **50 live page visits per click**. Selecting
hundreds is fine: the already-verified ones resolve for free, so pressing the
button again continues where the last run stopped rather than re-spending the
budget on the same first fifty.

That is the same pace as a normal scan and a fraction of its volume, and the
reason is the address it runs from. A block lands on the very home connection
your scheduled scans depend on, so if the portal starts refusing, the check
**stops after three refusals in a row** and says so. Insisting would only
deepen the block. Wait and retry later.

You can also stop a run yourself with the **⏹ Stop** button next to the
progress bar. It finishes whatever listing is already in flight — there is no
way to interrupt a live request — and leaves the rest of the selection
unchecked; re-select it later to pick up where you left off.

## When DataDome keeps interrupting

Turn on **"Run the check through the browser"** in **Settings** (under the
automatic cookie section). The check then runs through a real local browser
(headless) that earns a genuine cookie once and reuses it, instead of a fresh
request per ad — so it does not collect a 403 per listing. Slower per ad, but
it does not stop mid-run. This needs the optional browser engine installed, the
same one as the automatic cookie grab.

If DataDome still challenges even that browser with a CAPTCHA, tick **"Show the
browser window during the check"** right below it. Because you start the check
yourself and watch it run, the browser opens **visible**: solve the CAPTCHA once
in the window and the run continues on its own — that single solve earns a real
cookie the rest of the batch reuses, so you are not asked again. The window
waits a few minutes for you; if you ignore it, the check falls back to stopping
rather than hanging.

**This option shows nothing when the app runs as the NSSM Windows service**
(see [Running it 24/7 on Windows](remote-access.md#running-it-247-on-windows-no-window-to-keep-open)):
a Windows service has no desktop of its own (Session 0), so there is no screen
to open a window on, and the check runs headless regardless of the tick box. If
a run under the service gets blocked, don't wait on a window that will never
appear — click **"Grab a fresh cookie now"** (same Settings page, under
*Automatic cookie grab*) first. That button *does* pop a real, visible window
even with the service running, because it relaunches the browser inside your own
logged-in desktop session rather than the service's. Solve the CAPTCHA there
once. It shares the same on-disk browser profile as the availability check, so
the fresh, unblocked session carries over to the next run automatically.

## Being challenged less in the first place

Switch the **Browser engine** (same Settings section) to **Camoufox** — a
stealth Firefox that hides the automation signals DataDome looks for, so it is
flagged far less often than plain Chromium. It is a one-click install (~150 MB,
one time); leave the engine on **Auto** and it is used automatically once
installed, falling back to Chromium if anything goes wrong.

While a check runs, a **Transport** line under the progress bar tells you
exactly what it is using — "camoufox (visible window)", "fast requests (curl)",
or "browser off: no option enabled" — so you can see at a glance why a run
behaved the way it did instead of guessing.

Whenever the browser is in play, the app also **behaves like a person on each
page**: the mouse drifts along curved paths, the page scrolls a little, there is
a brief pause before reading. Anti-bot systems score behavior too, and a page
visited with zero pointer events looks robotic. This adds about a second per
page and is on by default; a checkbox in the same Settings section ("Move the
mouse and scroll like a person…") turns it off for the old, faster behavior.

You can also paste the `datadome` cookie from your real browser into the field
next to the button (it is stored with the other settings), or route the app's
traffic through a proxy configured in **Settings**.
