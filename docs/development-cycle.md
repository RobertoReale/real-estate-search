# The Development Cycle

How a change gets made in this repository, from "something is wrong" to "it is released".

This is a *procedure*, like [`audit.md`](audit.md), and it owns only the procedure: what the
rules are lives in [`invariants.md`](invariants.md), how code is written and tested lives in
[`conventions.md`](conventions.md), what each module does lives in
[`architecture.md`](architecture.md), and why the design is what it is lives in
[`../implementation_plan.md`](../implementation_plan.md). This file says in which order those
are used, and what has to be true before a commit exists at all.

Where a list or a number belongs to another file, this one links to it instead of repeating
it. A copied gate list is the copy that goes stale, and it goes stale in the file people
read *first*.

---

## 1. The unit of work

**One unit of work, one branch, one commit.**

A unit is a change that can be stated in a sentence and reviewed in one sitting: a bug with
its regression test, a feature with its invariant and its documentation, a dependency bump
with the evidence that the thing it feeds still works. If describing it needs the word
"and" twice, it is two units.

The branch is cut from `master` and named for the unit (`plan/phase-<n>` is what the history
uses), and it is merged back with a merge commit — `git merge --no-ff`, never a
fast-forward:

- **One commit per unit, because of `git revert`.** A unit you dislike a month later comes
  out with `git revert <sha>` (or `git revert -m 1 <merge>`), taking its tests and its
  documentation with it, without anyone having to work out which three of six commits were
  the feature and which were the fixes to the feature. Half a unit reverted is worse than
  none.
- **A merge commit, because the branch name is the only surviving description.** Branches
  are cheap and get forgotten; `git log --merges` afterwards is a list of the units this
  project was actually built out of, which is a shorter and more honest history than the
  list of commits.
- **No work-in-progress commits.** A commit that never had green gates is a commit
  `git bisect` will eventually stop on, and it will waste the session it stops in. Squash
  the exploration; commit the conclusion.

A fix small enough to need no branch — a one-line correction, a version number, a typo in a
doc — goes straight onto `master`. The history has both, and the rule is not "always branch"
but "never leave a unit half-committed".

Commit messages are [Conventional Commits](https://www.conventionalcommits.org/):
`fix(scrapers): …`, `feat: …`, `docs: …`, `chore(deps): …`. The subject says what changed;
the body says *why*, which is the part that is not recoverable from the diff.

---

## 2. Before every commit: the gates

Six gates: backend tests, pyright, `ruff check`, `ruff format --check`, the frontend build,
the frontend tests. The commands and the expected numbers are in
[`audit.md` §0](audit.md#0-green-baseline-run-first-every-audit) — that is the one place
they are written, so run them from there.

Three things about the timing, each of which has cost a session at least once:

- **Green *before* the commit, not before the merge.** The gates are cheap; a bisect
  through a run of commits nobody verified is not.
- **`ruff format --check` counts.** It is the easiest of the six to skip, because
  `ruff check` passing feels like "lint is green". CI runs both, so a commit that skipped it
  is green locally and red on the very next push.
- **Green on Windows is not green.** CI runs every gate on `ubuntu-latest` as well, because
  the Raspberry Pi is a real target. The failure this catches is invisible locally: a
  Windows-only call site (`ctypes.windll`) type-checks fine on Windows and fails on Linux,
  which is why it carries a targeted suppression (see
  [`conventions.md` → Writing code](conventions.md#writing-code)).

`.pre-commit-config.yaml` arms `ruff check`, `ruff format`, `pyright` and — when
`requirements.txt` itself changes — `pip-audit`, so the fast gates run whether or not you
remembered them:

```bash
cd backend && .venv\Scripts\python -m pre_commit install
```

It is a safety net, not the gate list: it does not run the test suites, and a green hook is
not a green baseline.

### What runs without being asked

Two automations exist so that a project nobody has touched for four months still reports its
own state:

- **CI runs weekly** (`.github/workflows/ci.yml`, Mondays), not only on push. A yanked
  dependency, a rebuilt runner image or an action version that stopped resolving produces no
  push, so without the schedule it surfaces the next time someone needs the project to work.
  GitHub disables a scheduled workflow after 60 days of repository silence and mails the
  owner: that mail is the signal, not noise — re-enable it.
- **Dependency updates arrive as pull requests** (`.github/dependabot.yml`), monthly and
  grouped per ecosystem. The frontend one is an ordinary diff. The backend one is a *notice
  that an update exists*, not a diff to merge: the three `requirements*.txt` are compiled
  from the `.in` files beside them, so the pin is moved in the `.in` and all three locks are
  recompiled ([`README.md` → Dependency
  locking](../README.md#dependency-locking)) and pushed over the branch.

---

## 3. New behaviour that can be wrong gets an invariant and a test

A test proves the behaviour is right today. An invariant records *why it must stay right*,
so the next person deletes the guard on purpose rather than by accident.

Add to [`invariants.md`](invariants.md), in the form that file already uses: the rule, the
regression that put it there, the code home, and the test that would fail if it broke. An
invariant with no history behind it is a preference, and preferences belong in
[`conventions.md`](conventions.md); an invariant with no test is a claim.
[`audit.md` §1](audit.md#1-invariant-audit-are-they-true-are-they-necessary) cross-checks
all three, so a missing half is found by the next audit rather than by the next regression.

The test itself follows [`conventions.md` → Testing](conventions.md#testing): offline,
deterministic, and — when it comes from a bug found on a real portal — carrying the
backstory in a comment, because the next reader's first instinct will be that the assertion
looks arbitrary.

---

## 4. Documentation is part of the change

[`conventions.md` → Documentation Is Part of the
Change](conventions.md#documentation-is-part-of-the-change) owns this rule and the table of
which file owns what. The cycle's part is only the timing: **the documentation edit is in
the same commit as the code**, not in a follow-up. A doc corrected three sessions later has
already misled someone, and a doc corrected in its own commit is a doc that a revert of the
feature leaves behind, still describing something that no longer exists.

Before committing, ask what the change made untrue. The numbers are the ones that rot
silently — the test count appears in [`audit.md` §0](audit.md#0-green-baseline-run-first-every-audit),
in [`conventions.md` → Testing](conventions.md#testing) and in `implementation_plan.md` §7,
and all three must match a real `pytest -q` run rather than each other.

---

## 5. Releasing

A release is a tag. Everything else is automatic.

1. **`master` is green** — the six gates locally, CI green on both operating systems for the
   commit being tagged.
2. **The two version numbers are in step**: `backend/pyproject.toml` and
   `frontend/package.json`. The halves ship as one artifact, so two different numbers are
   only ever a question nobody can answer.
3. **Tag and push**: `git tag v1.2.0 && git push origin v1.2.0`.

`.github/workflows/release.yml` triggers on `v*` and builds two things:

- **The Windows package.** `scripts/build_release.py --package` compiles the dashboard and
  freezes the tray app, the workflow then *launches the frozen binary* and requires both the
  API and the dashboard to answer before the bundle is zipped. A package that builds
  cleanly and cannot start is the failure the smoke test exists for, and PyInstaller cannot
  see it. The zip is attached to the GitHub release, which is what the "without installing
  anything" path in [`README.md`](../README.md) points people at.
- **The multi-arch image**, `linux/amd64` and `linux/arm64` (the Pi), pushed to `ghcr.io`
  tagged with the version and with `latest`.

Two deliberate omissions, both worth knowing before "improving" the workflow:

- **It re-runs none of the gates.** A tag points at a commit CI has already judged, and a
  second place to report the same failure is a second place for it to be flaky.
- **Nothing in CI or in the release ever reaches a real estate portal.** A blocked build
  runner would be harmless; the addresses the real scans depend on are not something to
  spend on a pipeline. The suite is offline by construction, which is what makes this
  cost-free rather than a compromise.

`workflow_dispatch` runs the same workflow against a branch: it builds and smoke-tests the
package and builds the image without pushing it, so the packaging can be exercised without
minting a version number to throw away.

---

## 6. What a finished unit looks like

- All six gates green, `ruff format --check` included, run before the commit.
- New behaviour that can be wrong has a test, and an invariant if breaking it would be
  silent.
- Every document the change made untrue is fixed in the same commit.
- One commit, on its own branch, merged with `--no-ff`.
- Nothing deferred into a `TODO:` comment or a "future work" section — it gets done, gets an
  issue, or gets dropped.
