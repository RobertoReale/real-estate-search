# What Only a Person Can Test

The gates prove the logic. They never prove the world.

[`audit.md` §0](audit.md) lists everything a machine can decide, and
[§3](audit.md#3-known-weak-points-to-check-explicitly) states the limit of it in one
sentence: a green suite means *the logic is correct*, not *the portal still parses*. This
file is what follows from that sentence — the checks a person has to perform themselves
before a release is called good, in the order to perform them, with the right answer
written down for each so that "it looked fine" is not an available verdict.

Run it against the commit that is about to be tagged, on the machine that actually runs
scans, from the residential connection those scans go out on. It takes an evening plus one
overnight wait; item 2 cannot be hurried, which is why it starts the same evening as item 1
and is read the next morning.

## The three rules this list is held to

**Only what automation cannot do.** Every item below states the reason no gate reaches it,
and the reason is always structural: a credential that arrives on a device, a challenge
minted for the visitor who asked, a market that has to publish something, or a pair of eyes.
Anything on this list that a test could have covered is a missing test, not a manual
step — write the test and delete the item. A checklist that quietly absorbs work the suite
should be doing becomes a ritual nobody performs and a gap nobody sees.
[§ What is deliberately not here](#what-is-deliberately-not-here) names the checks that were
considered for this list and rejected because a gate already owns them.

**When a tool reaches an item, the item is deleted.** Not kept beside the tool: two places
that check the same thing means running the stale one without knowing. What is left behind
is one line naming the command, in [§ What a tool decides now](#what-a-tool-decides-now),
because this file is the index of what a release is held to and not only of what a person
does. Five of the original nine checks left that way, and the numbers they had are in that
table — a reference to "item 6" written before cycle 4 means the upgrade check, which is now
a script.

**It ends in a verdict, not a feeling.** Every item is pass or fail, and every failure is
already classified: it either **blocks the release** or it is a **known limit** already
written down in [`limits.md`](limits.md), in which case the correct action is to confirm the
app still says so on screen and move on. There is no third category. If a failure fits
neither, that is the finding — it is a new limit or a new bug, and it gets written down
before the tag.

---

## The scorecard

Copy this, fill it in, keep it with the release notes. Run the tool-owned checks first: they
are mechanical, they cost an evening's worth of nothing, and two of the six items below only
make sense once a real scan has happened.

### What a person still does

| # | Check | Verdict | On failure |
|---|---|---|---|
| 1 | [Every credential, used for real](#1-every-credential-used-for-real) | pass / fail | **blocks** |
| 2 | [A notification for a genuinely new listing](#2-a-notification-for-a-genuinely-new-listing) | pass / fail | **blocks** |
| 3 | [A challenge solved by hand](#3-a-challenge-solved-by-hand) | pass / fail | known limit unless it crashes a scan |
| 4 | [The map at real scale](#4-the-map-at-real-scale) | pass / fail | known limit unless pins are wrong |
| 5 | [The phone, over Tailscale](#5-the-phone-over-tailscale) | pass / fail | **blocks** |
| 6 | [The frozen bundle's first scan](#6-the-frozen-bundles-first-scan) | pass / fail | **blocks** |

Four of the six block. That is the point of classifying them in advance: the ones that block
are the ones where a failure means the artifact is wrong, and the ones that do not are the
ones where a failure means the artifact is honest about something it cannot do.

### What a tool decides now

One line each, with the command. None of these is a manual step any more, and none of them
is repeated in prose below — the tool's own output is the verdict, and the document that owns
each tool is linked beside it.

| Was | Runs it now | Command | Green means |
|---|---|---|---|
| 1 — a real scan against both portals | `app.livecheck`, then the end-to-end run it grew in cycle 4: a backend of its own on 8138 with a throwaway data directory, the reference shapes created through the API the dashboard posts to, one full scan, and the **journal row** read rather than the tool's summary ([`live-checks.md`](live-checks.md#measurements--2026-09-13-the-real-scan-path-end-to-end)) | `cd backend && .venv\Scripts\python -m app.livecheck --suite` | exit 0 — every reference shape had a rung that answered, with a count consistent with the total the portal declared and the fields inside the cards checked, not just counted |
| 2 — the form against the same search pasted as a URL | `--compare-form` for the two totals and the review that has to predict the gap between them; `npm run e2e` for the screen, which drives the review in the dashboard as part of its control inventory (`profiles.review.confirm`, `profiles.review.verifyZone`) | `cd backend && .venv\Scripts\python -m app.livecheck --compare-form` | every difference between the pasted total and the form-built one is named by the review beside it — an unpredicted gap is the failure, a predicted one is [`limits.md`](limits.md) working |
| 6 — the upgrade, and the way back from it | `scripts/check_upgrade.py`, against a copy of the database the previous release wrote. It never writes to the file it is pointed at, migrates a copy on port 8139, and asserts the schema, the row counts, every curated field, the `case-pre-*` snapshot surviving rotation, download, restore's 409 under a held scan flag, and import | `cd backend && .venv\Scripts\python ..\scripts\check_upgrade.py --db backups\<the-previous-release-copy>.db` | every line `[PASS]`, exit 0. A `WARN` that no properties were compared means the database was empty — point it at one with a scan in it |
| 7 — the package on a machine with no toolchain | `scripts\windows\sandbox-smoke.ps1`, in Windows Sandbox: a throwaway Windows with no Python, no Node and no venv, driven by its logon command | `powershell -ExecutionPolicy Bypass -File scripts\windows\sandbox-smoke.ps1 -Zip RealEstateSearch-v2.0.0-windows-x64.zip` | eight steps PASS, exit 0, about three minutes. Exit 2 is "this machine cannot run the sandbox", and the reason is printed: then the check is a second PC again. `-Folder dist\RealEstateSearch` tests a local `build_release.py --package` instead of a published zip |
| 9 — the pull request queue, at the tag | three `gh` commands and one file comparison, immediately before tagging — no session, no person, but the *moment* is the release rather than any point in the cycle, which is why it is still written down | `gh pr list` · `gh run list --limit 5` · `gh workflow run release.yml --ref master` | nothing open that should have been merged, CI green on both operating systems for the exact commit being tagged, the versions in `backend/pyproject.toml` and `frontend/package.json` identical as [`development-cycle.md` §5](development-cycle.md#5-releasing) requires, and the dispatched release run green in both its jobs |

The sandbox and the upgrade script each leave one half behind, and both halves are items
above rather than footnotes here: the scan the sandbox cannot make because its networking is
off on purpose is [item 6](#6-the-frozen-bundles-first-scan), and the Settings screen the
upgrade script cannot look at — the backup list, a copy downloaded from the browser, a
different one restored over the live database — is the browser half of that script's own
output, to be done once its lines are green.

---

## 1. Every credential, used for real

**Why no tool reaches it.** Stored secrets are never in the test corpus.
`tests/conftest.py` points the suite away from the real `settings.json` on purpose
([invariant 17](invariants.md)), and the browser suite runs against a throwaway data
directory, so the code path that reads a real token and hands it to a real service has never
been executed by anything but a person. `app.livecheck` does not help here either: it reads
searches and never sends a message. [Invariant 27](invariants.md) is here because of exactly
this blind spot — a saved secret was once overwritten by its own `***` mask on the next save,
which no offline test could see until it was written to look for it. And the last link is a
device this repository cannot read: the phone the message arrives on.

**Do.** Two channels, each with the credential actually in place.

- **Telegram.** With the token and chat id saved, press the Telegram test in Settings
  (`POST /api/settings/telegram-test`). Then send the bot a command from the phone, so the
  polling half is exercised too, and press one of the action buttons on a real notification
  — [`notifications.md` → Telegram action buttons](notifications.md#telegram-action-buttons)
  lists what each does.
- **Mail.** Same, with the mail test. Gmail needs an app password rather than the account
  password; [`notifications.md` → Gmail](notifications.md#gmail-use-an-app-password) is the
  procedure.

Then **save Settings a second time without retyping anything** and re-run both tests. The
third credential — the DataDome cookie, the one the app mints rather than stores — is
[item 3](#3-a-challenge-solved-by-hand), because what makes it manual is the challenge and
not the saving.

**Pass.** A Telegram message arrives on the phone; a button on it changes the property in
the dashboard. A mail arrives. The second save changes nothing: both still work.

**Fail means.** A test that fails immediately is the credential or the channel toggle — both
error strings name what to check. A test that worked and then stopped after the second save
is [invariant 27](invariants.md) broken, and it blocks: a release that silently eats the
token on the next visit to Settings has removed the only channel the product speaks through.

---

## 2. A notification for a genuinely new listing

**Why no tool reaches it.** This is the end to end the whole product exists for, and it is
the one thing no fixture can stage. It needs a listing that did not exist when the baseline
was taken and does exist now — which means it needs the market to publish one, and the only
way to obtain that is to wait. The suite can prove that a synthetic new row produces a
notification, and does; it cannot prove that the real chain — portal publishes, scraper
parses, deduplicator decides it is not an existing property, filter engine keeps it,
notifier sends — holds end to end on real data. Every link in that chain is tested; the
chain is not.

**Only the last link is left, and it is the one nothing records.** The chain up to the
database is readable afterwards: `properties.first_seen_at` says when a property was first
stored, `price_history` holds the drop a second message would have announced, and the scan
journal row says which search on which portal read how many pages and how it ended. The two
links after that leave no trace. `scanner._dispatch_notifications` returns how many messages
it sent, and that number rides in the scan's own reply and nowhere else —
`scan_state["last_counts"]` counts new, updated, filtered and price changes and not it, the journal
(`scanner.get_scan_journal`) records pages, listings, outcome and stop reason but not
notifications, and it keeps its last forty entries **in memory**, so an app restart takes
them. The notifier logs only failures. So there is no table of past runs to fill in from
records and none is offered here: *"a genuinely new listing produced a notification since
date X"* is not a fact this app has ever stored, and this item is the only place it is
established. Read the journal the morning after, before the app is restarted.

**Do.** Start this the same evening as item 1 and read it a day later. The first scan of a
search sends nothing at all — it is building the baseline, and `baseline_done` is what gates
the silence ([invariant 3](invariants.md), and [`README.md`](../README.md#la-prima-scansione-è-diversa) →
*La prima scansione è diversa*). So: leave a search enabled on a city with real turnover and
let the scheduler run it again overnight.

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

## 3. A challenge solved by hand

**Why no tool reaches it.** A CAPTCHA is the one artifact on the internet built to need a
person, and DataDome's is minted in JavaScript for the visitor that asked, against the
address it asked from. Nothing offline can produce one: the suite serves `mock_portal`, and
a challenge cannot be simulated because what it measures is the browser and the IP, not the
request. Nothing automated can pass one either — the 2026-09-12 measurements in
[`live-checks.md`](live-checks.md#measurements--2026-09-12-why-every-free-local-rung-is-refused)
found the headless browser rung refused *harder* than `curl_cffi`, which is why the cookie
harvester opens the browser **visible** and waits for a person, and why the ad-availability
check offers the same escape hatch ([`availability-check.md`](availability-check.md)).

**Do.** Press "grab a fresh cookie now" in Settings and let it open a real browser. If a
challenge appears, solve it. Then run a search on the portal that was refusing. For a single
ad that keeps being challenged, tick "Show the browser" in the availability check and solve
it there once.

**Pass.** The cookie grab returns a value, `datadome_cookie_set` turns true, and the next
scan of a portal that was refusing gets an answer.

**Fail means.** The cookie grab reporting "not available" is **not** a failure: Playwright is
an optional ~300 MB dependency, the harvester is opt-in and fails open by design
([invariant 18](invariants.md)), and the manual path — copy the `datadome` cookie out of your
own browser and paste it into Settings — is the supported fallback
[`scan-returns-nothing.md`](scan-returns-nothing.md#give-the-scraper-a-real-browsers-cookie)
documents. A portal that stays blocked after everything that document offers is a known limit
until it is the *only* state the product is ever in, and then it blocks, because the
product's one job is not being done. A cookie grab that **crashes a scan** blocks on its own:
fail-open is the invariant.

---

## 4. The map at real scale

**Why no tool reaches it.** The browser suite runs against the demo corpus — eighty
synthetic properties, all invented, all in one city, deterministic by seed. That corpus is
what makes the map testable at all, and it is exactly why it cannot answer this question:
its coordinates are generated rather than geocoded, so nothing in it exercises Nominatim's
one-request-a-second pace (`geocode.pace`), the cached-miss path, or what a few hundred real
pins do to clustering and to the browser. Real scale is a property of real data, and what
"usable" means at every zoom is a judgement a pair of eyes makes.

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

## 5. The phone, over Tailscale

**Why no tool reaches it.** The browser suite serves loopback and always will, because
binding anything else on a CI runner is both meaningless and rude.
[Invariant 14](invariants.md) is precisely the rule that **the bind address is the access
control** — the API has no password, so where it listens is the whole security model — and
`serve.bat` binding somewhere other than loopback is the one path that rule governs and no
gate can execute. The suite proves nothing that changes state lives outside `/api` and that
cross-site writes are rejected; it cannot prove the socket ends up where you think, and it
has no second device to try the wrong network from.

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

## 6. The frozen bundle's first scan

**Why no tool reaches it.** `sandbox-smoke.ps1` now proves everything else about the package
on a machine that has never had the toolchain — it unzips, starts, answers on its own
loopback, serves the built dashboard, saves a setting, gets killed and comes back with it —
and the one thing it deliberately does not do is reach the network. The sandbox shares this
machine's connection, and the app scans real portals on a schedule from whatever host it runs
on, so an unbudgeted scan leaving from here is how this address gets blocked for a day
(invariant 8). Nothing else in the project ever makes a real request from **inside** the
frozen bundle: `app.livecheck` runs from the dev venv, so it proves the transports of the
source tree and never PyInstaller's copy of them, and a `curl_cffi` binary or a CA bundle
that did not get collected looks exactly like one that did until something asks for a page.
The failure is also mute: a windowed build has no console, so what it says when an import or
a data file is missing is a message box, and reading it needs eyes.

**Do.** On a machine you are watching — the sandbox will not do, this one will — unzip the
release bundle (or `dist\RealEstateSearch` from `python scripts\build_release.py --package`)
and double-click the executable. Complete the first-run setup, create **one** search on one
portal in a city with stock, and run one **quick** scan: one search's worth of requests, the
smallest thing that proves the bundle can reach a portal at all.

**Pass.** The journal row finishes `ok` with listings parsed and the properties appear in the
dashboard. No dialog reports a missing DLL, a missing interpreter or a missing data file.

**Fail means.** Blocks — this is the artifact most users get, and the "without installing
anything" path in [`README.md`](../README.md) points them straight at it. A certificate or SSL
error, or an import that fails only here, is a PyInstaller collection gap in
`packaging/realestatesearch.spec`; a missing data file is the same gap one directory over.
A row that comes back `blocked` is **not** this item's failure — that is the portal, and
[`scan-returns-nothing.md`](scan-returns-nothing.md) is the decision tree for it. What this
item is asking is whether the request left the frozen process at all.

---

## What is deliberately not here

The table above lists checks that *used* to be on this list and are now run by a tool. These
are the ones that were never on it: each was considered and rejected, because a gate already
owns it. They are recorded so nobody adds them back as a manual step:

- **Every control in the dashboard being reachable and working.** `npm run e2e` drives the
  assembled product and holds the run to a written inventory of every interactive element,
  with any unreachable one requiring a stated reason. A person clicking around is strictly
  worse at this than the suite.
- **Accessibility and horizontal scroll at phone, tablet and desktop widths.** Same suite,
  `axe-core` at 390, 768 and 1440 px. Item 5 is about the *socket*, not the layout.
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
  them; the journal row is read for what the *portal* did, not to re-verify the wording.

---

## When an item on this list stops being manual

Delete it. If a check here becomes reachable by a gate — a portal ships a stable API, a
service exposes a sandbox, a device becomes scriptable — the correct move is to write the
test and remove the item, not to keep both. Two places that check the same thing means
running the stale one without knowing — the same reasoning
[`conventions.md`](conventions.md) applies everywhere else here: one fact, one place.

That is not a hypothetical. In cycle 4 five of the nine items left this list: two to
`app.livecheck` and the end-to-end run around it, one to `check_upgrade.py`, one to Windows
Sandbox, and one to three `gh` commands — each of them written because the manual item it
replaces was the one that got skipped. What is left is six items, and the reason each one is
still here is a property of the world rather than a gap in the tooling: a device, a
challenge, a market, or a pair of eyes.

If a check *fails* and the failure turns out to be permanent rather than a bug, it stops
being a manual test and becomes a row in [`limits.md`](limits.md) — with what lifting it
would cost, so that "we know about it" and "we could fix it" stay different claims.
