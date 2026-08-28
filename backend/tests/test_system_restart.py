"""The backend-restart endpoint. The worker thread is stubbed out: letting it
run would touch a source file or (with reload off) os.execv the pytest process
itself, so every test asserts the endpoint's decision without ever executing the
restart body."""

import re
import sys

import pytest
from fastapi import HTTPException

from app.routers import system


class _FakeThread:
    """Captures the worker target without ever running it."""

    instances: list = []

    def __init__(self, target=None, daemon=None):
        self.target = target
        self.started = False
        _FakeThread.instances.append(self)

    def start(self):
        self.started = True


@pytest.fixture(autouse=True)
def _stub_thread(monkeypatch):
    _FakeThread.instances = []
    monkeypatch.setattr(system.threading, "Thread", _FakeThread)


def test_refused_while_a_scan_is_running(monkeypatch):
    monkeypatch.setitem(system.scan_state, "running", True)
    with pytest.raises(HTTPException) as e:
        system.system_restart()
    assert e.value.status_code == 409
    assert not _FakeThread.instances  # nothing scheduled


def test_reload_mode_touches_instead_of_reexec(monkeypatch):
    monkeypatch.setitem(system.scan_state, "running", False)
    monkeypatch.setenv("APP_RELOAD", "1")
    res = system.system_restart()
    assert res == {"ok": True, "reload": True}
    assert _FakeThread.instances[0].started is True


def test_no_reload_mode_reports_reexec_path(monkeypatch):
    monkeypatch.setitem(system.scan_state, "running", False)
    monkeypatch.delenv("APP_RELOAD", raising=False)
    res = system.system_restart()
    assert res == {"ok": True, "reload": False}
    assert _FakeThread.instances[0].started is True


# --- the argv the re-exec hands back to the interpreter ---------------------


def test_relaunch_quotes_every_argument_on_windows(monkeypatch):
    r"""Windows has no real execv: the CRT joins argv into one command line and
    quotes nothing, so a space in the interpreter path splits it in two. The
    replacement process then opened the wrong file and died, taking the backend
    down for good — on a path like `C:\Users\Mario Rossi\...`, which is the
    ordinary Windows case, not an exotic one.
    """
    monkeypatch.setattr(system.os, "name", "nt")

    argv = system.relaunch_argv(r"C:\Users\Mario Rossi\app\.venv\Scripts\python.exe", ["run.py"])

    assert argv == [r'"C:\Users\Mario Rossi\app\.venv\Scripts\python.exe"', '"run.py"']


def test_relaunch_survives_the_command_line_join_windows_will_do(monkeypatch):
    """The property that actually matters: what the CRT builds by joining the
    list with spaces must parse back into the original arguments."""
    monkeypatch.setattr(system.os, "name", "nt")
    executable = r"C:\Program Files\Real Estate\python.exe"

    joined = " ".join(system.relaunch_argv(executable, ["run.py"]))

    assert _win_parse(joined) == [executable, "run.py"]


def _win_parse(command_line: str) -> list[str]:
    """Split a command line the way Windows itself does.

    Uses the real CommandLineToArgvW when running on Windows, so the assertion
    is against the actual parser rather than an imitation of it; elsewhere a
    minimal stand-in covers the only quoting form this helper emits.

    Asks sys.platform, not os.name: the callers patch os.name to "nt" to make
    the code under test take the Windows branch, and that patch lands on the os
    module itself, so it is visible here too. On Linux that sent this helper
    into the ctypes branch, where importing ctypes with os.name == "nt" makes
    CPython's own ctypes/__init__ look for a Windows-only symbol and fail. The
    question here is which machine we are on, and only sys.platform answers it.
    """
    if sys.platform == "win32":  # pragma: no branch - platform-dependent
        import ctypes
        from ctypes import wintypes

        ctypes.windll.shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
        ctypes.windll.shell32.CommandLineToArgvW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(ctypes.c_int),
        ]
        count = ctypes.c_int(0)
        argv_ptr = ctypes.windll.shell32.CommandLineToArgvW(command_line, ctypes.byref(count))
        try:
            return [argv_ptr[i] for i in range(count.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(argv_ptr)
    return _naive_parse(command_line)


def _naive_parse(command_line: str) -> list[str]:
    """The stand-in for CommandLineToArgvW used off Windows."""
    return [token.strip('"') for token in re.findall(r'"[^"]*"|\S+', command_line)]


def test_the_stand_in_parser_agrees_with_windows_on_what_this_helper_emits():
    """Each machine only runs half of _win_parse: Windows takes the real parser,
    CI takes the stand-in. Test the stand-in everywhere, or the branch that CI
    actually depends on is only ever exercised where nobody looks at it."""
    assert _naive_parse(r'"C:\Program Files\x\python.exe" "run.py"') == [
        r"C:\Program Files\x\python.exe",
        "run.py",
    ]


def test_relaunch_leaves_the_list_alone_on_posix(monkeypatch):
    """execv takes the list verbatim there, so a quote would become part of the
    argument rather than delimit it."""
    monkeypatch.setattr(system.os, "name", "posix")

    assert system.relaunch_argv("/usr/bin/python3", ["run.py"]) == ["/usr/bin/python3", "run.py"]
