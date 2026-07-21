# Email Inbox Import

[← Back to README](../README.md)

If the portals already mail you their alerts, point the
app at your mailbox (IMAP) and it collects the listing links from those emails.
Your mailbox is opened **strictly read-only** — nothing is deleted, and messages
are not even marked as read. Imported listings are staged in a review list and
enter the dashboard only when you accept them, going through the same
deduplication as a normal scan. A scan of a large mailbox takes minutes, and a
progress bar reports how many emails it has read so far. Once the first import
is done, tick **"Re-scan the inbox automatically"** in **Settings** to have the
app pick up newly arrived alert emails on a schedule (every few hours up to
once a week). New listings are added to the review list silently — you are not
notified and nothing enters the dashboard until you accept it, exactly like a
manual scan.

Review cards show only what the email itself contained: price, surface, rooms,
the €/m² derived from them, and the alert's subject line (usually the name of
the saved search, the one hint of *where* the property is). The panel never
opens the ad pages — mass-visiting hundreds of old listings would be slow and
a good way to get blocked — so anything else means clicking **Open ↗**. Sort by
€/m² to rank them by value rather than by sticker price.

Alert emails also link each ad several times: from its photo, from a "see the
listing" button, and from the footer's *"if the link does not work, copy this
address"*. Links the email describes with nothing at all are skipped rather
than staged, since there would be nothing to review them by.

Emails are often months old, so many of those ads are already sold. Select the
ones you care about and press **Check if still online**: the app opens each
ad page once and marks the removed ones, which you can then discard in one go.
If the portal refuses to answer (a block, a timeout), the listing is left
exactly as it was — a listing wrongly reported as gone would be discarded
forever, so silence never counts as proof. Listings the dashboard already
tracks as live are resolved from the local database without contacting the
portal at all, and already-checked listings are skipped when checking in bulk
(re-select a single one to force a fresh check). If the portal blocks the
check anyway, you can paste the `datadome` cookie from your real browser into
the field next to the button (it is stored with the other settings), or route
the app's traffic through a proxy configured in **Settings**.

The check is deliberately slow: it visits the portal's homepage first (as a
browser would), then one ad page every 6–8 seconds, at most 50 live page
visits per click — selecting hundreds is fine, the already-verified ones skip
for free, so pressing the button again continues where the last run stopped.
Same pace as a normal scan, and one tenth of its volume. If the portal starts
refusing anyway, the check **stops after three refusals in a row** and says so:
insisting would only deepen the block, and the block would land on the same
home connection your scheduled scans need. In that case, wait and retry later.
You can also stop a run yourself at any time with the **⏹ Stop** button next to
the progress bar — it finishes whatever listing is already in flight (there is
no way to interrupt a live request mid-flight) and leaves the rest of the
selection unchecked; re-select it later to pick up where you left off.

If DataDome keeps interrupting the check, turn on **"Run the check through the
browser"** in **Settings** (under the automatic cookie section). The check then
runs through a real local browser (headless) that earns a genuine cookie once
and reuses it, instead of a fresh request per ad — so it does not collect 403
blocks. It is slower per listing, but it does not stop mid-run. This needs the
optional browser engine installed (same one as the automatic cookie grab).

If DataDome still challenges even that browser with a CAPTCHA, tick **"Show the
browser window during the check"** right below it. Because you start the check
yourself and watch it run, the browser opens **visible**: when a CAPTCHA
appears, solve it once in the window and the run continues on its own — that
single solve earns a real cookie the rest of the batch reuses, so you are not
asked again. The window waits a few minutes for you; if you ignore it, the
check falls back to stopping rather than hanging.

**This option shows nothing when the app runs as the NSSM Windows service**
(see [Running it 24/7 on Windows](remote-access.md#running-it-247-on-windows-no-window-to-keep-open)):
a Windows service has no desktop of its own (Session 0), so there is no screen
to open a window on, and the check just runs headless regardless of the tick
box. If a run under the service gets blocked, don't wait on a window that will
never appear — instead click **"Grab a fresh cookie now"** (same Settings page,
under *Automatic cookie grab*) first. That button *does* pop a real, visible
window even with the service running, because it specifically relaunches the
browser inside your own logged-in desktop session rather than the service's;
solve the CAPTCHA there once. It shares the same on-disk browser profile as the
availability check, so the fresh, unblocked session it earns carries over to
the next "Check online availability" run automatically — you don't need to run
anything interactively for this to work.

To be challenged less in the first place, switch the **Browser engine** (same
Settings section) to **Camoufox** — a stealth Firefox that hides the automation
signals DataDome looks for, so it is flagged far less often than plain
Chromium. It is a one-click install (~150 MB, one time); leave the engine on
**Auto** and it is used automatically once installed, falling back to Chromium
if anything goes wrong. While a check runs, a **Transport** line under the
progress bar tells you exactly what it is using — "camoufox (visible window)",
"fast requests (curl)", or "browser off: no option enabled" — so you can see at
a glance why a run behaved the way it did instead of guessing.

Whenever the browser is in play, the app also **behaves like a person on each
page** — the mouse drifts along curved paths, the page scrolls a little,
there is a brief pause before reading — because anti-bot systems score
behavior too, and a page visited with zero pointer events looks robotic.
This adds about a second per page and is on by default; a checkbox in the
same Settings section ("Move the mouse and scroll like a person…") turns it
off if you want the old, faster bare-visit behavior.

**Only ads hosted on Immobiliare.it or Idealista.it can be imported**, since
the app identifies a listing by its portal ID. An agency that mails you its
own proposals (Tecnocasa, a local agency, …) is imported only if the email
links a portal ad; if it links the agency's own website, searching for that
sender finds the email and imports nothing from it.

The two buttons are not symmetric, so when in doubt accept: an accepted listing
becomes a normal property you can still hide, while a discard is remembered
forever — that memory is what stops a re-scan from resurfacing it.
