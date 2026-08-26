"""Produces the payload a release ships, starting with the built dashboard.

The end user must never need Node. The React app is compiled here, once, by
whoever cuts the release, and the resulting `frontend/dist` travels inside the
package — the backend already mounts it at "/" (invariant 13), so serving it
needs nothing but Python at run time.

`dist` is gitignored on purpose: it is a build artifact, and a checked-in one
would rot behind the sources it came from. That makes this script the only
thing standing between "the release contains a dashboard" and "the release
contains an empty folder and a 404", which is why it verifies the payload
rather than trusting that npm exited 0.

Run it directly to build and check:  python scripts/build_release.py
"""

import sys
from pathlib import Path

import build_frontend

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"

# What a servable build contains. `assets/` holds the hashed JS and CSS bundles;
# the manifest and the two icons are what makes the dashboard installable as an
# app icon on a phone, and a release that quietly dropped them would still serve
# a working dashboard - the failure would only show up as "Add to home screen"
# producing a blank icon, months later and nowhere near this code.
REQUIRED = ("index.html", "assets", "manifest.webmanifest", "icon-192.png", "icon-512.png")


def verify_payload() -> list[str]:
    """Returns the list of missing pieces; empty means the payload is complete."""
    return [name for name in REQUIRED if not (DIST / name).exists()]


def payload_size_bytes() -> int:
    return sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())


def build_frontend_payload() -> int:
    """Builds `frontend/dist` and verifies it is complete. 0 on success.

    The packaging steps call this before bundling: PyInstaller and Docker both
    copy the folder wholesale, and neither would notice it was empty.
    """
    if build_frontend.main() != 0:
        return 1

    missing = verify_payload()
    if missing:
        print(
            f"[ERROR] The frontend build is incomplete - missing: {', '.join(missing)}.\n"
            f"        Looked in {DIST}. Delete the folder and build again;\n"
            "        an interrupted build leaves a partial one behind.",
            file=sys.stderr,
        )
        return 1

    print(f"[RELEASE] Dashboard payload ready: {DIST} ({payload_size_bytes() / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_frontend_payload())
