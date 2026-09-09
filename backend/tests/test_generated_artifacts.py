"""Checks on the files this repository commits but does not write by hand.

Two of them — `frontend/src/types/api.ts` and the npm lockfiles — are produced by
a tool, reviewed as a diff, and installed from verbatim. Both broke in the same
way: the artifact was wrong in the repository while every local gate reported
green, because the gates re-ran the tool that had produced it rather than
reading what it produced. CI on Linux said so for weeks and nobody was reading
CI, which is the second half of the same failure.

So these assertions read the committed bytes and nothing else. They need no
network, no `node_modules` and no npm — that is the point, since the npm on this
machine is exactly the one that accepted the broken lock.

- **The lockfiles.** A package that declares `bundleDependencies` ships those
  packages inside its own tarball, and npm still requires each of them to have a
  resolved entry in the lock. `frontend/package-lock.json` named three of
  `@tailwindcss/oxide-wasm32-wasi`'s six and omitted `@emnapi/core` and
  `@emnapi/runtime`; npm 11.6.2 installs that lock without complaint and the
  npm 11.19 on the runner refuses it, so `npm ci` failed five of the eight CI
  jobs from the merge of phase 0.4 onward while nothing here could see it.
  `npm ci --dry-run` is not a substitute: it short-circuits on a populated
  `node_modules` and exits 0, and so does a run against a copy of the tree.

- **`api.ts`.** Invariant 23 — see `scripts/gen_api_types.py`, where the fix is.
"""

import ast
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "gen_api_types.py"
API_TYPES = ROOT / "frontend" / "src" / "types" / "api.ts"

# Every "â€", "Ã " and friend starts here: a UTF-8 lead byte that arrived in the
# file as the cp1252 character of the same value.
MOJIBAKE_MARKERS = ("â€", "Ã¨", "Ã©", "Ã ", "Â°", "Â»")


# Pruned rather than filtered: an unpruned walk descends into node_modules and
# .venv, which is tens of thousands of directories on every collection.
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", "__pycache__"}


def _lockfiles() -> list[Path]:
    """The npm lockfiles this repository owns, never the ones inside a package."""
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(ROOT):
        subdirectories[:] = [name for name in subdirectories if name not in SKIP_DIRS]
        if "package-lock.json" in filenames:
            found.append(Path(directory) / "package-lock.json")
    return sorted(found)


def _bundled_is_resolved(packages: dict[str, dict], owner: str, bundled: str) -> bool:
    """npm's own lookup: the owner's own `node_modules`, then each ancestor's."""
    candidates = [f"{owner}/node_modules/{bundled}"]
    prefix = owner
    while "node_modules/" in prefix:
        prefix = prefix.rpartition("node_modules/")[0].rstrip("/")
        candidates.append(f"{prefix}/node_modules/{bundled}".lstrip("/"))
    return any(candidate in packages for candidate in candidates)


def test_repository_has_lockfiles_to_check() -> None:
    """A rename that moves them out of reach must not turn this file into a no-op."""
    assert _lockfiles(), "no package-lock.json found — has the frontend moved?"


@pytest.mark.parametrize("lockfile", _lockfiles(), ids=lambda p: str(p.relative_to(ROOT)))
def test_every_bundled_dependency_has_a_resolved_entry(lockfile: Path) -> None:
    """What the runner's npm enforces and the npm on this machine does not."""
    packages = json.loads(lockfile.read_text(encoding="utf-8")).get("packages", {})
    missing = [
        f"{owner} bundles {bundled}"
        for owner, meta in packages.items()
        for bundled in meta.get("bundleDependencies") or []
        if not _bundled_is_resolved(packages, owner, bundled)
    ]
    assert not missing, (
        f"{lockfile.relative_to(ROOT)} has no resolved entry for: {', '.join(missing)}. "
        "`npm ci` rejects this on a newer npm than the one here — regenerate the lock "
        "with the Node version .github/workflows/ci.yml pins."
    )


def test_the_type_generator_decodes_its_subprocess_explicitly() -> None:
    """Invariant 23: `text=True` alone decodes with the platform's locale.

    Read off the call rather than the file: the module writes `spec.json` and
    `api.ts` with an explicit encoding too, so a substring search for
    `encoding="utf-8"` anywhere in the source stays satisfied by those while the
    `subprocess.run` that matters loses its own — which is the exact edit this
    is here to refuse.
    """
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]
    assert runs, "scripts/gen_api_types.py no longer runs the generator as a subprocess"
    for call in runs:
        encodings = [kw.value for kw in call.keywords if kw.arg == "encoding"]
        assert encodings and all(
            isinstance(value, ast.Constant) and value.value == "utf-8" for value in encodings
        ), (
            "scripts/gen_api_types.py captures the generator without an explicit encoding: "
            "on Windows its UTF-8 output is decoded as cp1252 and committed corrupted."
        )


def test_the_generated_api_types_are_not_mojibake() -> None:
    """The evidence the gate above exists to stop reappearing."""
    text = API_TYPES.read_text(encoding="utf-8")
    found = [marker for marker in MOJIBAKE_MARKERS if marker in text]
    assert not found, (
        f"frontend/src/types/api.ts contains {found} — it was generated on a machine that "
        "decoded the generator's UTF-8 output with a legacy locale. Regenerate it."
    )
