"""Regenerates `frontend/src/types/api.ts` from the backend's OpenAPI document.

The frontend used to carry a hand-maintained twin of `backend/app/schemas.py`:
two files, six hundred lines each, and nothing that made them agree. A field
renamed on the backend became a silent `undefined` in the browser, at runtime,
with every gate green — which is exactly the failure a type system is bought to
prevent. So the wire types are no longer written by hand: they are derived from
the document FastAPI already publishes.

The result is **committed**, for two reasons. The frontend must build with no
backend running (CI's frontend job has no Python), and a generated file in the
diff is what makes a wire change visible in review rather than invisible until
someone opens the app.

Run it after changing anything a route sends or accepts:

    python scripts/gen_api_types.py

CI runs the same command and then `git diff --exit-code` on the generated file,
so a schema edited without regenerating is a red build and not a bug report.

`APP_DATA_DIR` is pointed at a scratch folder before the app is imported: the
document is a pure function of the code, and generating it must not create a
log, a database or a settings file anywhere the user would find one.

The generator itself lives in `scripts/apitypes/`, with its own manifest and its
own lock, and that separation is not tidiness. `openapi-typescript` links against
the TypeScript compiler API and its peer range still pins that to 5.x, while this
app is built with TypeScript 7; npm resolves a peer at the root of a tree and
refuses to nest one, so installed beside the frontend the tool loads the app's
compiler and dies on `ts.factory` being undefined. Its own tree is what lets both
versions be exactly what each needs.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
GENERATOR = ROOT / "scripts" / "apitypes"
TARGET = ROOT / "frontend" / "src" / "types" / "api.ts"

HEADER = """/** The backend's wire format, generated from its OpenAPI document.
 *
 *  Do not edit: run `python scripts/gen_api_types.py` instead. CI regenerates
 *  this file and fails on any difference, so an edit here is undone on the next
 *  push while the schema it disagreed with stays as it was.
 *
 *  `frontend/src/types/index.ts` is where these are given their working names;
 *  it is also where the types that exist only in the browser live.
 */
"""


def openapi_document(scratch: Path) -> dict:
    """The app's own OpenAPI document, with no side effects on the user's data."""
    os.environ["APP_DATA_DIR"] = str(scratch)
    sys.path.insert(0, str(BACKEND))
    from app.main import app  # noqa: PLC0415 — after APP_DATA_DIR, or it is too late

    document = app.openapi()
    # Importing the app opens its rotating log inside the scratch folder, and on
    # Windows a directory holding an open handle cannot be removed.
    logging.shutdown()
    return document


def generate(document: dict, scratch: Path) -> str:
    """The document run through the pinned `openapi-typescript`.

    `--no-install`, so a missing `node_modules` is a readable error rather than
    npx quietly fetching whatever version is newest today — this file is
    committed and compared, and the tool that writes it has to be the one the
    lock names.
    """
    spec = scratch / "openapi.json"
    spec.write_text(json.dumps(document, indent=2), encoding="utf-8")
    result = subprocess.run(
        # shell=True on Windows: npx is a .cmd shim CreateProcess will not run
        # directly. Every part of this command is a constant except the path,
        # which this process just wrote.
        f'npx --no-install openapi-typescript "{spec}"',
        cwd=GENERATOR,
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(
            "[ERROR] openapi-typescript failed. Run `npm ci` in scripts/apitypes/ "
            "first — that is where the generator's own toolchain is pinned."
        )
    return result.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="api-types-") as tmp:
        scratch = Path(tmp)
        body = generate(openapi_document(scratch), scratch)
    # Written with explicit LF whatever the platform: the file is committed, and
    # the gate that compares it must not turn a Windows checkout into a diff.
    TARGET.write_text(HEADER + "\n" + body.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(f"[TYPES] Wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
