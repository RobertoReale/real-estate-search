"""The backend-restart endpoint. The worker thread is stubbed out: letting it
run would touch a source file or (with reload off) os.execv the pytest process
itself, so every test asserts the endpoint's decision without ever executing the
restart body."""
import pytest
from fastapi import HTTPException

from app import main


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
    monkeypatch.setattr(main.threading, "Thread", _FakeThread)


def test_refused_while_a_scan_is_running(monkeypatch):
    monkeypatch.setitem(main.scan_state, "running", True)
    with pytest.raises(HTTPException) as e:
        main.system_restart()
    assert e.value.status_code == 409
    assert not _FakeThread.instances  # nothing scheduled


def test_reload_mode_touches_instead_of_reexec(monkeypatch):
    monkeypatch.setitem(main.scan_state, "running", False)
    monkeypatch.setenv("APP_RELOAD", "1")
    res = main.system_restart()
    assert res == {"ok": True, "reload": True}
    assert _FakeThread.instances[0].started is True


def test_no_reload_mode_reports_reexec_path(monkeypatch):
    monkeypatch.setitem(main.scan_state, "running", False)
    monkeypatch.delenv("APP_RELOAD", raising=False)
    res = main.system_restart()
    assert res == {"ok": True, "reload": False}
    assert _FakeThread.instances[0].started is True
