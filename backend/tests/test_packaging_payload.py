"""What the two shippable builds are allowed to contain.

Both of them copy directories wholesale rather than files by name — the
PyInstaller spec ships `backend/app/data` and `frontend/dist` as trees, and
`packaging/Dockerfile` does `COPY backend/ ./` under `.dockerignore` — which is
the right call for a payload that grows, and the wrong shape for anything
secret. The user's credentials live in `backend/settings.json` and their
database in `backend/case.db`, both a directory level above what is shipped, and
both one careless `mv` away from being inside it. An image or a release ZIP that
carries them is not a bug anyone notices: it works perfectly, and it hands the
portal cookies and the Telegram token to whoever downloads it.

So these assertions read the two manifests and the trees they name. They need
no PyInstaller, no Docker and no built frontend — the point is that the answer
is knowable before the build runs, not after it has been published.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "packaging" / "realestatesearch.spec"
DOCKERIGNORE = ROOT / ".dockerignore"

# Named for what they hold, not for where they sit: the check is that a file
# with one of these names is nowhere inside a shipped tree, wherever it came
# from. `*.log` is here because the scan journal quotes portal responses.
SECRET_NAMES = re.compile(
    r"""^(
        settings\.json      # every credential the app stores
        | case\.db(-wal|-shm)?  # the user's whole corpus, and their searches
        | \.env(\..*)?      # not read by this app, and read by half the tooling
        | .*\.log(\.\d+)?   # app.log, which quotes what the portals answered
        | .*\.(pem|key|pfx)
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

# Directories a shipped tree may legitimately contain and that hold nothing of
# the user's, pruned rather than filtered so the walk stays cheap.
SKIP_DIRS = {"__pycache__", "node_modules", ".git"}


def _spec_datas() -> list[Path]:
    """The paths the PyInstaller spec ships, read as text rather than executed.

    Executing it would need PyInstaller installed, which is deliberately not in
    the dev venv (see `requirements-package.txt`), and would run a build script
    inside the test suite to answer a question about its source.
    """
    source = SPEC.read_text(encoding="utf-8")
    block = source.split("datas = [", 1)[1].split("]", 1)[0]
    paths: list[Path] = []
    for match in re.finditer(r"str\(([^)]+)\)", block):
        parts = re.findall(r'"([^"]+)"', match.group(1))
        base = ROOT if match.group(1).lstrip().startswith("ROOT") else ROOT / "backend"
        if parts:
            paths.append(base.joinpath(*parts))
    return paths


def _offending_files(tree: Path) -> list[str]:
    if tree.is_file():
        return [tree.name] if SECRET_NAMES.match(tree.name) else []
    found: list[str] = []
    for path in tree.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and SECRET_NAMES.match(path.name):
            found.append(str(path.relative_to(ROOT)))
    return found


def test_the_spec_still_declares_the_payload() -> None:
    """A rename or a refactor of the spec must not turn the checks below green by
    finding nothing to check."""
    datas = _spec_datas()
    assert datas, "no datas parsed out of the spec — has its shape changed?"
    assert ROOT / "backend" / "app" / "data" in datas


@pytest.mark.parametrize("tree", _spec_datas(), ids=lambda p: p.name)
def test_the_packaged_build_carries_nothing_of_the_users(tree: Path) -> None:
    """Each tree the spec ships, checked for the files that must never leave.

    `frontend/dist` is skipped when it has not been built: this runs in CI
    before the frontend stage and the assertion is about what a tree contains,
    not about whether it exists.
    """
    if not tree.exists():
        pytest.skip(f"{tree.relative_to(ROOT)} is not built here")
    assert _offending_files(tree) == []


def test_the_docker_context_excludes_the_users_files() -> None:
    """The image copies `backend/` entire, so `.dockerignore` is the only thing
    standing between the user's credentials and a published layer."""
    ignored = {
        line.strip()
        for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    for required in (
        "backend/case.db",
        "backend/settings.json",
        "backend/app.log*",
        "backend/backups/",
        "**/.env",
    ):
        assert required in ignored, f"{required} is not excluded from the build context"
