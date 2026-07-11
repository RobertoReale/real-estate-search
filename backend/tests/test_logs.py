"""Tests for the in-app log viewer (GET /api/logs/tail).

Without this endpoint, "is the scan/check actually doing anything?" could
only be answered by opening app.log by hand — this exists so the dashboard
can show the same file. The endpoint is called directly (see test_features.py):
spinning up TestClient would also start the real scheduler via the app lifespan.
"""
from app import main as app_main


def test_missing_log_file_returns_an_empty_list(monkeypatch, tmp_path):
    monkeypatch.setattr(app_main, "LOG_PATH", tmp_path / "does-not-exist.log")
    result = app_main.logs_tail()
    assert result["lines"] == []


def test_tail_returns_only_the_last_n_lines(monkeypatch, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join(f"line {i}" for i in range(10)), encoding="utf-8")
    monkeypatch.setattr(app_main, "LOG_PATH", log_file)

    result = app_main.logs_tail(lines=3)

    assert result["lines"] == ["line 7", "line 8", "line 9"]
    assert result["path"] == str(log_file)


def test_tail_defaults_to_two_hundred_lines(monkeypatch, tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("\n".join(f"line {i}" for i in range(500)), encoding="utf-8")
    monkeypatch.setattr(app_main, "LOG_PATH", log_file)

    result = app_main.logs_tail()

    assert len(result["lines"]) == 200
    assert result["lines"][-1] == "line 499"
