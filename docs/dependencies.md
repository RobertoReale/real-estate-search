# Dependencies

Every dependency this project has is pinned, in a generated lockfile, so the
same checkout installs the same application on any machine and at any point in
the future. This page is how those locks are regenerated and what goes wrong
when they are not.

## The Python lockfiles

`backend/requirements.txt`, `requirements-dev.txt` and `requirements-package.txt`
are **generated** lockfiles: every package pinned to the exact version, with
hashes, so the same checkout installs the same application on any machine and at
any point in the future. Edit the `.in` file beside them and recompile with
[uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv pip compile requirements.in --universal --python-version 3.11 --generate-hashes -o requirements.txt
uv pip compile requirements-dev.in --universal --python-version 3.11 --generate-hashes -o requirements-dev.txt
uv pip compile requirements-package.in --universal --python-version 3.11 --generate-hashes -o requirements-package.txt
```

Recompile **all three** after touching `requirements.in`: the other two `.in`
files start with `-r requirements.in`, so a runtime pin that moves in one and not
the others leaves the packaged Windows build installing a different version from
the one the gates ran against.

## The frontend lock

The frontend is locked the same way by `frontend/package-lock.json`. Install it
with **`npm ci`, never `npm install`**: `ci` installs exactly what the lock pins
and fails loudly if the lock and `package.json` disagree, where `install`
quietly rewrites the lock and gives that machine a different toolchain. The
start scripts and CI both use `npm ci`, so the only time `npm install` is right
is when you are deliberately adding or upgrading a dependency — and then the
rewritten lock is part of the change and gets committed with it.

```bash
cd frontend
npm ci
```

## The api-types project

There is a second, much smaller npm project at `scripts/apitypes/`, locked and
installed the same way. It holds nothing the application ships — only
`openapi-typescript`, which `scripts/gen_api_types.py` uses to compile the
backend's OpenAPI document into `frontend/src/types/api.ts`. It lives apart
because that tool links against the TypeScript compiler API and still pins it to
5.x, while the app is built with TypeScript 7; npm resolves a peer dependency at
the root of a tree and refuses to nest one, so installed beside the frontend the
generator would load the app's compiler and fail. Its own tree lets each have
exactly the version it needs.

```bash
cd scripts/apitypes
npm ci
```

## Regenerating an npm lock

Regenerating either npm lock is the one step with a trap in it, and the trap has
two jaws. Never `npm install --package-lock-only`: with no materialised tree npm
resolves a thinner one and writes a lock that `npm ci` afterwards rejects as out
of sync, and the failure names a transitive package nothing depends on directly
(`@emnapi/core`, reached through Tailwind's optional wasm fallback), so it reads
like a registry outage rather than a malformed lock. And never delete
`package-lock.json` first: `@tailwindcss/oxide-wasm32-wasi` names that package
and five others in `bundleDependencies`, npm writes their nested entries only
when it is updating a lock that already carries them, so a lock built from a bare
`package.json` omits all six — which is what `test_generated_artifacts.py` fails
on.

Upgrade in place instead. Edit `package.json`, leave the existing lock where it
is, and run `npm install` over it:

```bash
cd frontend
npm install
```

Run that on Linux, with the Node version `.github/workflows/ci.yml` pins. The
wasm subtree is skipped on Windows, so an install there quietly drops entries the
runner's `npm ci` then refuses, and the build is red on a lock that looked fine
locally. CI pins that version exactly for the same family of reasons: npm 10 and
npm 11 disagree about what a valid lock is, and one written by the other fails
`npm ci` on a checkout that is otherwise perfectly fine.

## What Dependabot opens

Neither lock has to be watched by hand: `.github/dependabot.yml` opens one
grouped pull request per ecosystem per month. Both are a **notice, not a diff**:
each names versions worth taking and rewrites a generated file on a machine that
is not set up the way this one is. The frontend one carries a
`package-lock.json` written without the bundled wasm subtree above; take the
versions it names, put them in `package.json`, and regenerate the lock as
described. The backend one edits a generated lock without
touching the `.in` file the lock is compiled from. Take the version it names,
move the pin in the `.in`, recompile all three as above, and push that over the
branch.

## Optional developer tooling

Beyond the runtime dependencies, an optional dev toolchain (linting, coverage,
property-based tests, dependency CVE scanning, and a pre-commit hook) lives in
`backend/requirements-dev.txt`. It is **never** installed on the target device —
only in a development checkout (it includes the runtime set, so it is the only
file a developer needs to install):

```bash
cd backend
& .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
& .venv/Scripts/ruff.exe check app tests      # lint
& .venv/Scripts/ruff.exe format app tests     # format
& .venv/Scripts/python.exe -m pip_audit -r requirements.txt   # CVE scan
```

