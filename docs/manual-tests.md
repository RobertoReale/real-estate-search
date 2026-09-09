# What Only a Person Can Test

The gates prove the logic. They never prove the world.

[`audit.md` §0](audit.md) lists everything a machine can decide, and
[§3](audit.md#3-known-weak-points-to-check-explicitly) states the limit of it in one
sentence: a green suite means *the logic is correct*, not *the portal still parses*. This
file is what follows from that sentence — the nine checks a person has to perform
themselves before a release is called good, in the order to perform them, with the right
answer written down for each so that "it looked fine" is not an available verdict.

Run it against the commit that is about to be tagged, on the machine that actually runs
scans, from the residential connection those scans go out on. It takes an evening plus one
overnight wait; item 4 cannot be hurried, which is why it starts early.

## The two rules this list is held to

**Only what automation cannot do.** Every item below states the reason no gate reaches it,
and the reason is always structural: the network, a credential, a machine, a device, or
time. Anything on this list that a test could have covered is a missing test, not a manual
step — write the test and delete the item. A checklist that quietly absorbs work the suite
should be doing becomes a ritual nobody performs and a gap nobody sees.
[§ What is deliberately not here](#what-is-deliberately-not-here) names the checks that were
considered for this list and rejected because a gate already owns them.

**It ends in a verdict, not a feeling.** Every item is pass or fail, and every failure is
already classified: it either **blocks the release** or it is a **known limit** already
written down in [`limits.md`](limits.md), in which case the correct action is to confirm the
app still says so on screen and move on. There is no third category. If a failure fits
neither, that is the finding — it is a new limit or a new bug, and it gets written down
before the tag.

---

## The scorecard

Copy this, fill it in, keep it with the release notes.

| # | Check | Verdict | On failure |
|---|---|---|---|
| 1 | [A real scan against both portals](#1-a-real-scan-against-both-portals) | pass / fail | **blocks** |
| 2 | [The form against the same search pasted as a URL](#2-the-form-against-the-same-search-pasted-as-a-url) | pass / fail | mostly a known limit — see the item |
| 3 | [Every credential, used for real](#3-every-credential-used-for-real) | pass / fail | **blocks** |
| 4 | [A notification for a genuinely new listing](#4-a-notification-for-a-genuinely-new-listing) | pass / fail | **blocks** |
| 5 | [The map at real scale](#5-the-map-at-real-scale) | pass / fail | known limit unless pins are wrong |
| 6 | [The upgrade, and the way back from it](#6-the-upgrade-and-the-way-back-from-it) | pass / fail | **blocks** |
| 7 | [The package on a machine with no toolchain](#7-the-package-on-a-machine-with-no-toolchain) | pass / fail | **blocks** |
| 8 | [The phone, over Tailscale](#8-the-phone-over-tailscale) | pass / fail | **blocks** |
| 9 | [The pull request queue, at the tag](#9-the-pull-request-queue-at-the-tag) | pass / fail | **blocks** |

Five of the nine block. That is the point of classifying them in advance: the ones that
block are the ones where a failure means the artifact is wrong, and the ones that do not are
the ones where a failure means the artifact is honest about something it cannot do.

---

## 1. A real scan against both portals

**Why no gate reaches it.** This is the only check that proves the scrapers still parse.
The offline suite serves `mock_portal` — HTML this repository wrote — so it proves the
parsing *strategy* and can never notice that the portal changed its markup last night.
DataDome cannot be simulated at all: the challenge is minted by JavaScript in a real browser
against the IP that asked, and [`development-cycle.md` §5](development-cycle.md#5-releasing)
records that nothing in CI or in the release workflow ever touches a real estate portal, on
purpose. A portal that changed overnight and a portal that did not are byte-identical to
every gate in this repository.

**Do.** From the residential connection, with the app running: create one search per portal
in a city you know — Milan is a safe control because it always has stock — and run a **full**
scan of each. Read the scan journal row, not just the grid.

**Pass.** Both rows finish `ok`. Each reports a listing count in the same order of magnitude
as the portal's own result header for the same search, opened in a browser side by side.
Titles are real titles, prices are real prices, and the zone on a card is a zone rather than
portal boilerplate. A row marked `incomplete` because it hit `max_pages_per_search` is a
pass — that is the page cap doing its job, and the row says so.

**Fail means.** `Error` on a row is the parsers: the portal moved something and
`scrapers/html_cards.py` no longer finds the card container. Start at
[invariant 2](invariants.md) — the recovery is a new structural heuristic, never a CSS class,
and the invariant explains why. Zero listings from Immobiliare with no error is usually
[invariant 7](invariants.md): the geo parameters did not resolve, and an unresolvable
location must never have widened into a nationwide search. `Blocked` is **not** a failure of
this item on its own — it is the expected state the whole of
[`scan-returns-nothing.md`](scan-returns-nothing.md) exists for. Grab a fresh cookie
(item 3), leave from a different address, and retry; only a portal that stays blocked after
everything that document offers is a release blocker, and then it is a blocker because
the product's one job is not being done.

---

## 2. The form against the same search pasted as a URL

**Why no gate reaches it.** The two entry points are not equally expressive, and the
difference only shows in the totals a real portal returns. A pasted Immobiliare URL can
carry a drawn polygon (`vrt`), a radius around a point (`centro` + `raggio`) and an
isochrone; the builder form has no field that can say any of those, which is the limit
`profiles.areaNeedsUrl` in [`limits.md`](limits.md) already names. On the other side,
`search_builder.idealista_unsupported()` lists what Idealista cannot express *at all* —
an excellent/renovated condition, a room cap of five or more, and any drawn area or radius,
which its grammar cannot state, so its half of a paired search becomes the whole comune.
The suite proves that function returns the right list. Only a live run proves what the two
totals actually are, and the gap between them is the thing that reads as a deduplication
bug when it is really a filter that is not there.

**Do.** Build one search in the form. Then open the same search on Immobiliare in a browser,
copy its URL, and paste it into a second search. Run both. Compare the totals per portal,
and read the **search review** on both — it is the screen that prints, per portal, which
parameters were widened (`profiles.reviewApprox`) and which were dropped
(`profiles.reviewDropped`).

**Pass.** For a search the form can express fully, the two totals agree within the noise of
listings appearing and disappearing between the two runs. For a search the form cannot
express — anything drawn — the pasted URL returns fewer, tighter results than the form's
city-wide equivalent, **and the review says so before the scan rather than after**. Wherever
Idealista's half is the wider one, `idealista_unsupported` has already named the parameter
it dropped.

**Fail means.** A difference the review did not predict is the failure. A silently wider
Idealista half with an empty "dropped" cell is a missing entry in `idealista_unsupported()`
— and its docstring warns that the last two additions turned out to be parameters that did
exist under a name nobody had read off the portal yet, so check the portal's own UI before
adding one. A totals gap with a full, accurate review is **not** a failure: it is
[`limits.md`](limits.md) working exactly as designed, and the correct verdict is pass.

---

## 3. Every credential, used for real

**Why no gate reaches it.** Stored secrets are never in the test corpus.
`tests/conftest.py` points the suite away from the real `settings.json` on purpose
([invariant 17](invariants.md)), and the browser suite runs against a throwaway data
directory, so the code path that reads a real token and hands it to a real service has never
been executed by anything but a person. [Invariant 27](invariants.md) is here because of
exactly this blind spot — a saved secret was once overwritten by its own `***` mask on the
next save, which no offline test could see until it was written to look for it.

**Do.** Three things, each with the credential actually in place.

- **Telegram.** With the token and chat id saved, press the Telegram test in Settings
  (`POST /api/settings/telegram-test`). Then send the bot a command from the phone, so the
  polling half is exercised too, and press one of the action buttons on a real notification
  — [`notifications.md` → Telegram action buttons](notifications.md#telegram-action-buttons)
  lists what each does.
- **Mail.** Same, with the mail test. Gmail needs an app password rather than the account
  password; [`notifications.md` → Gmail](notifications.md#gmail-use-an-app-password) is the
  procedure.
- **The DataDome cookie.** Press "grab a fresh cookie now" and let it open a real browser.
  This is the one credential the app mints rather than stores.

Then **save Settings a second time without retyping anything** and re-run all three tests.

**Pass.** A Telegram message arrives on the phone; a button on it changes the property in
the dashboard. A mail arrives. The cookie grab returns a value, `datadome_cookie_set` turns
true, and the next scan of a portal that was refusing gets an answer. The second save
changes nothing: all three still work.

**Fail means.** A test that fails immediately is the credential or the channel toggle — both
error strings name what to check. A test that worked and then stopped after the second save
is [invariant 27](invariants.md) broken, and it blocks. The cookie grab reporting
"not available" is **not** a failure: Playwright is an optional ~300 MB dependency, the
harvester is opt-in and fails open by design ([invariant 18](invariants.md)), and the manual
path — copy the `datadome` cookie out of your own browser and paste it into Settings — is
the supported fallback [`scan-returns-nothing.md`](scan-returns-nothing.md#give-the-scraper-a-real-browsers-cookie)
documents. A cookie grab that *crashes a scan* is a blocker, because fail-open is the
invariant.

---

## 4. A notification for a genuinely new listing

**Why no gate reaches it.** This is the end to end the whole product exists for, and it is
the one thing no fixture can stage. It needs a listing that did not exist when the baseline
was taken and does exist now — which means it needs the market to publish one, and the only
way to obtain that is to wait. The suite can prove that a synthetic new row produces a
notification, and does; it cannot prove that the real chain — portal publishes, scraper
parses, deduplicator decides it is not an existing property, filter engine keeps it,
notifier sends — holds end to end on real data. Every link in that chain is tested; the
chain is not.

**Do.** Start this at item 1 and read it a day later. The first scan of a search sends
nothing at all — it is building the baseline, and `baseline_done` is what gates the silence
([invariant 3](invariants.md), and [`README.md`](../README.md#la-prima-scansione-è-diversa) →
*La prima scansione è diversa*). So:
after item 1's first scan, leave the search enabled and let the scheduler run it again
overnight on a city with real turnover.

**Pass.** The first scan sends nothing, however many listings it found. A later scan sends a
notification for a listing that is genuinely new, the message links to the ad, and clicking
through lands on a live page for that property. A price drop on a property already in the
dashboard sends its own message, and the figure in it is the change in the **minimum** price
across the merged listings ([invariant 6](invariants.md)).

**Fail means.** Notifications on the first scan is [invariant 3](invariants.md) broken and
blocks — it is the failure mode that floods a phone with hundreds of messages, which is the
regression that put the invariant there. Silence on the second scan when the portal clearly
has new stock is either the deduplicator merging a new property into an old one, or the
filter engine discarding it: the journal row and the property's own history say which. A
notification for a listing that is not new means the fingerprint changed under a property
that did not — start at [invariant 1](invariants.md). "…and *N* more" at the end of a batch
is not a failure; it is `max_notifications_per_scan` naming what it suppressed, which is the
last row of the [`limits.md`](limits.md) inventory.

---

## 5. The map at real scale

**Why no gate reaches it.** The browser suite runs against the demo corpus — eighty
synthetic properties, all invented, all in one city, deterministic by seed. That corpus is
what makes the map testable at all, and it is exactly why it cannot answer this question:
its coordinates are generated rather than geocoded, so nothing in it exercises Nominatim's
one-request-a-second pace (`geocode.pace`), the cached-miss path, or what a few hundred real
pins do to clustering and to the browser. Real scale is a property of real data.

**Do.** After several real scans have accumulated a few hundred properties, run "find
coordinates" to completion and open the map. Zoom from the whole city down to a single
street. Open a pin whose property has only a zone and no street address.

**Pass.** Geocoding finishes, its progress line stays honest about the pace it is held to,
and re-running it does not redo work already cached. The map stays usable at every zoom;
clusters split into the right pins. A property placed by zone centroid says so — in the
pin's own popup and in the legend's count — and is never presented as an address. That is
[invariant 24](invariants.md), and it is the one thing on this item that blocks.

**Fail means.** A zone centroid shown as if it were the address blocks the release: it is a
lie about where a flat is, and someone will drive to it. Slowness at a few hundred pins is a
**known limit**, not a blocker — the pace and the approximation are both in the
[`limits.md`](limits.md) inventory with what lifting them would cost, and the correct action
is to confirm the app still says so on screen.

---

## 6. The upgrade, and the way back from it

**Why no gate reaches it.** `test_migrations.py` proves a fresh database is stamped at the
baseline and upgraded cleanly, and it is a real check — but it starts from a database this
repository created. The database that matters is the one the *previous release* wrote, on
this machine, holding months of price history that no re-scan can rebuild. The suite has
never seen it and cannot: it is one file, on one disk, and it is the whole point of the
product. Likewise `restore` is unit-tested against fixtures; the question here is whether a
real backup taken by the shipped app on the previous version restores into this one.

**Do.** On a **copy** of the real `case.db`, start the new build and let it migrate. Then, in
Settings, list the backups: confirm the pre-upgrade snapshot (`case-pre-*`) that
`database._snapshot_before_upgrade` takes is there. Download one copy through the browser,
and restore a different one back over the live database. Finally, import a `case.db` carried
from another install.

**Pass.** The migration completes and the dashboard opens with every property, every price
point and every curated field — favourites, notes, tags, hidden and sold flags — still
attached. The `case-pre-*` snapshot exists and is outside the daily rotation, so it does not
get pruned. Restore refuses while a scan is running (409) and succeeds when one is not. The
downloaded file opens in any SQLite reader — that is the honest answer to "am I locked in".

**Fail means.** Any of this blocks. Data lost or curated fields reset in a migration cannot
be undone by re-scanning and is the worst failure this product has; the pre-upgrade snapshot
is the seatbelt, and a missing snapshot is as serious as a bad migration because it removes
the only way back. Restore succeeding mid-scan blocks too: it swaps the file under a process
writing properties and their profile links, and leaves both half-written.

---

## 7. The package on a machine with no toolchain

**Why no gate reaches it.** The release workflow builds the one-folder bundle and launches
the frozen binary, requiring the API and the dashboard to answer before the zip is attached
— a real smoke test, and it is the reason this item is short. What it cannot be is a machine
that has never had the toolchain. The runner has Python, Node and a venv installed by the
job that precedes it, so a bundle that silently depends on any of them passes there and
fails in the only place it matters: someone else's PC.

**Do.** Take the zip from the GitHub release (or `dist\RealEstateSearch\` from
`python scripts\build_release.py --package`) to a Windows machine with **no Python, no Node
and no venv** — a fresh user account is not enough, it must be a machine that has not been
developed on. Unzip it and double-click the executable. Complete the first-run setup, save a
setting, run one scan.

**Pass.** The tray app starts, the dashboard opens in a browser, the API answers, settings
persist across a restart, and the scan reaches a portal. No console window reports a missing
DLL, a missing interpreter or a missing data file.

**Fail means.** Blocks the release — this is the artifact most users get, and the "without
installing anything" path in [`README.md`](../README.md) points them straight at it. A
missing data file is almost always a PyInstaller collection gap in
`packaging/realestatesearch.spec`; a missing module is an import that only ever resolved
because the dev venv had it.

---

## 8. The phone, over Tailscale

**Why no gate reaches it.** The browser suite serves loopback and always will, because
binding anything else on a CI runner is both meaningless and rude.
[Invariant 14](invariants.md) is precisely the rule that **the bind address is the access
control** — the API has no password, so where it listens is the whole security model — and
`serve.bat` binding somewhere other than loopback is the one path that rule governs and no
gate can execute. The suite proves nothing that changes state lives outside `/api` and that
cross-site writes are rejected; it cannot prove the socket ends up where you think.

**Do.** Run `scripts\windows\serve.bat` with Tailscale up. Open the dashboard from the phone
over the tailnet. Then, from another device on the same physical LAN that is **not** on the
tailnet, try the same address and port.

**Pass.** The phone loads the dashboard and the API answers it. The off-tailnet device
cannot connect at all. Every screen is usable at phone width — that part the browser suite
does check at 390 px, so this is confirmation rather than the point. If you deliberately
used `serve.bat lan`, the warning it prints about binding `0.0.0.0` with no password appears,
and the LAN device *does* connect: that is the documented trade, not a bug.

**Fail means.** Blocks. An off-tailnet device reaching an unauthenticated API when
`serve.bat` was run without `lan` is invariant 14 broken, and the exposure is the whole
database. [`remote-access.md`](remote-access.md) owns the setup; this item owns proving it.

---

## 9. The pull request queue, at the tag

**Why no gate reaches it.** Not because it is hard, but because of *when*. The sequence's
own task clears what is open at the moment it runs; Dependabot opens more every week
afterwards, and no task can close a pull request that does not exist yet. This is the one
check whose correct time is the moment of release rather than any point in the cycle, which
is why it is here and last.

**Do.** Immediately before tagging: `gh pr list` and `gh run list --limit 5`. Check the two
version numbers are in step — `backend/pyproject.toml` and `frontend/package.json` — as
[`development-cycle.md` §5](development-cycle.md#5-releasing) requires. Then start the
release workflow by hand against the commit about to be tagged —
`gh workflow run release.yml --ref master` — and read it to the end. It publishes nothing
off a branch: the image push and the release creation are both gated on the ref being a tag,
so what a dispatch proves is the expensive half, that the package still freezes, starts and
answers, and that both images still build.

**Pass.** Nothing open that should have been merged, CI green on both operating systems for
the exact commit being tagged, the two version numbers identical, and the dispatched release
run green in both its jobs.

**Fail means.** Blocks, and for the first two cheaply: merge or close the queue, or wait for
the run. A tag re-runs no gates — it points at a commit CI has already judged — so a red
pipeline at the tag ships a build nothing verified. A red release dispatch is the same
argument one workflow later, and the one worth the extra ten minutes: on the tag those same
jobs run with a public release attached to their outcome, and the repair is a half-published
version to withdraw rather than a branch to fix.

---

## What is deliberately not here

Each of these was considered for this list and rejected, because a gate already owns it.
They are recorded so nobody adds them back as a manual step:

- **Every control in the dashboard being reachable and working.** `npm run e2e` drives the
  assembled product and holds the run to a written inventory of every interactive element,
  with any unreachable one requiring a stated reason. A person clicking around is strictly
  worse at this than the suite.
- **Accessibility and horizontal scroll at phone, tablet and desktop widths.** Same suite,
  `axe-core` at 390, 768 and 1440 px. Item 8 is about the *socket*, not the layout.
- **Visual regressions.** `npm run e2e:visual`, pixel-diffed against a Linux baseline in CI.
  A human eye is the wrong instrument for a two-pixel padding shift, and the baselines must
  never be written anywhere but on the runner that reads them.
- **What the dashboard costs to open.** The Lighthouse budget in CI, in bytes rather than
  timings, precisely so it does not depend on who is watching.
- **The committed API types matching the backend.** Regenerate-and-diff, plus the byte-level
  assertions in `test_generated_artifacts.py` that exist because re-running a tool and
  comparing it against itself is not a check ([invariant 23](invariants.md)).
- **Whether a scan reports itself completely and honestly** — the page cap, the quick-scan
  label, the segmented-search partition. Those are invariants 28 and 29 with tests behind
  them; item 1 reads the journal row to confirm the *portal*, not to re-verify the wording.

---

## When an item on this list stops being manual

Delete it. If a check here becomes reachable by a gate — a portal ships a stable API, a
service exposes a sandbox, a device becomes scriptable — the correct move is to write the
test and remove the item, not to keep both. Two places that check the same thing means
running the stale one without knowing — the same reasoning
[`conventions.md`](conventions.md) applies everywhere else here: one fact, one place.

If a check *fails* and the failure turns out to be permanent rather than a bug, it stops
being a manual test and becomes a row in [`limits.md`](limits.md) — with what lifting it
would cost, so that "we know about it" and "we could fix it" stay different claims.
