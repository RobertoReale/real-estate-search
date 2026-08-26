"""Builds the React app into `frontend/dist` when it is missing or out of date.

`start.bat` serves the built app from the backend's own port, so the dashboard
the user opens is whatever sits in `frontend/dist`. Without a staleness check
that folder silently becomes a snapshot of some earlier checkout: the app runs,
nothing errors, and the user is looking at last month's UI.

Timestamps, not hashes: a rebuild costs a second and a half, so the cheap
comparison is the right one. The newest source file wins against the newest
build artifact, which means a `git pull` that rewrites one component triggers a
rebuild while a plain restart does not.

Exit codes: 0 = `dist` is ready to serve, 1 = it is not (and why is on stderr).
Run it directly to force the decision: `python scripts/build_frontend.py`.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"

# Everything the build reads. `node_modules` is deliberately absent: it is huge,
# npm rewrites mtimes inside it on every install, and a dependency change is
# already visible through package-lock.json.
SOURCE_FILES = ("index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json")
SOURCE_DIRS = ("src", "public")


def _newest_mtime(paths) -> float:
    newest = 0.0
    for path in paths:
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            # A file that vanished mid-walk cannot be newer than the build in
            # any way we can prove, so it simply does not vote.
            continue
    return newest


def _source_mtime() -> float:
    files = [FRONTEND / name for name in SOURCE_FILES]
    for name in SOURCE_DIRS:
        files.extend(p for p in (FRONTEND / name).rglob("*") if p.is_file())
    return _newest_mtime(files)


def _dist_mtime() -> float:
    if not (DIST / "index.html").is_file():
        return 0.0  # no build at all, or one interrupted before it wrote the entry point
    return _newest_mtime(p for p in DIST.rglob("*") if p.is_file())


def build_needed() -> bool:
    dist = _dist_mtime()
    return dist == 0.0 or _source_mtime() > dist


def _npm(command: str) -> int:
    # shell=True on Windows: npm is a .cmd shim, which CreateProcess will not
    # run directly. Every command passed here is a constant.
    try:
        return subprocess.run(command, cwd=FRONTEND, shell=True).returncode
    except OSError:
        return 127


def main() -> int:
    if not build_needed():
        print("[BUILD] Frontend is up to date.")
        return 0

    if not DIST.is_dir():
        print("[BUILD] No frontend build found - building it now (first run takes a moment)...")
    else:
        print("[BUILD] Frontend sources changed - rebuilding...")

    # Node is only needed when there is something to build. A release ships a
    # prebuilt `dist` with no sources newer than it, so this whole branch is
    # skipped and the user never installs Node at all.
    if not (FRONTEND / "node_modules").is_dir():
        print("[SETUP] Installing frontend dependencies...")
        # `ci`, not `install`: it installs exactly what package-lock.json pins
        # and refuses if the lock disagrees with package.json, where `install`
        # would quietly rewrite the lock.
        if _npm("npm ci") != 0:
            print(
                "[ERROR] Installing the frontend dependencies failed (npm ci).\n"
                "        Node.js 18+ must be installed and on PATH, and the machine\n"
                "        needs an internet connection for the first install.",
                file=sys.stderr,
            )
            return 1

    if _npm("npm run build") != 0:
        print("[ERROR] The frontend build failed - see the npm output above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
