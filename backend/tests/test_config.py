"""Tests for the settings file's compatibility with its own past versions.

A settings.json on a user's disk outlives the code that wrote it. When a
feature is removed its keys stay in that file, and the app has to keep reading
it — an unknown key must be inert, never an error, or removing a feature would
break every installation that had ever configured it.
"""

import json
import os
from pathlib import Path

from app import config
from app.config import DEFAULT_SETTINGS, load_settings, save_settings


def _settings_file(tmp_path, monkeypatch, contents: dict | None = None) -> Path:
    """Point config at a throwaway file (invariant 17), optionally seeded with
    what a previous version of the app would have left there."""
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    if contents is not None:
        path.write_text(json.dumps(contents), encoding="utf-8")
    return path


def test_settings_from_a_previous_version_still_load(tmp_path, monkeypatch):
    """A key belonging to a since-removed feature must not stop the file from
    loading, and must not disturb the keys around it."""
    _settings_file(
        tmp_path, monkeypatch, {"scan_interval_minutes": 15, "a_removed_feature_flag": True}
    )

    settings = load_settings()

    assert settings["scan_interval_minutes"] == 15
    # every current key is still served, from the defaults where the file is silent
    assert set(DEFAULT_SETTINGS) <= set(settings)
    assert settings["telegram_enabled"] is DEFAULT_SETTINGS["telegram_enabled"]


def test_saving_over_an_older_file_keeps_working(tmp_path, monkeypatch):
    """Writing settings back is the moment a stale key would blow up. It does
    not: the obsolete entry is carried along untouched rather than inspected,
    so a downgrade still finds what it left behind."""
    path = _settings_file(tmp_path, monkeypatch, {"a_removed_feature_flag": True})

    saved = save_settings({"scan_interval_minutes": 30})

    assert saved["scan_interval_minutes"] == 30
    assert json.loads(path.read_text(encoding="utf-8"))["a_removed_feature_flag"] is True


def test_save_settings_refuses_keys_that_are_not_settings(tmp_path, monkeypatch):
    """The write path is filtered against DEFAULT_SETTINGS, so a typo or a
    stale field posted by an out-of-date frontend cannot invent a setting."""
    _settings_file(tmp_path, monkeypatch)

    saved = save_settings({"scan_interval_minutes": 45, "not_a_setting": "x"})

    assert saved["scan_interval_minutes"] == 45
    assert "not_a_setting" not in saved


# --- corruption is survivable, but never silent -----------------------------


def test_an_unreadable_settings_file_is_logged_not_swallowed(tmp_path, monkeypatch, caplog):
    """Regression: the fallback to defaults was a bare `except: pass`.

    Every secret the app has lives in this file, so running on the defaults
    means the API auth gate silently switching itself off (invariant 14's
    sanctioned way to widen the bind stops gating anything), notifications
    stopping, and scrapes losing their DataDome cookie — all at once, with
    nothing written anywhere. Worse, the next save then persists those defaults
    over whatever survived. The app must still start, but it has to say so."""
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    path.write_text('{"telegram_bot_token": "abc", "api_auth_to', encoding="utf-8")  # truncated

    with caplog.at_level("ERROR"):
        settings = load_settings()

    assert settings["api_auth_token"] == DEFAULT_SETTINGS["api_auth_token"]  # still starts
    assert any("settings.json" in r.getMessage() for r in caplog.records), (
        "an unreadable settings file must be reported, not swallowed"
    )


def test_saving_settings_is_atomic(tmp_path, monkeypatch):
    """A plain write_text truncates before it writes, so a crash or a full disk
    mid-save leaves a settings.json that load_settings cannot parse — and the
    app comes back on the defaults with every secret gone. The write goes to a
    sibling temp file and is renamed into place, so the real file is either the
    old contents or the new ones, never half of either."""
    path = _settings_file(tmp_path, monkeypatch, {"scan_interval_minutes": 15})

    real_replace = os.replace
    seen: dict = {}

    def spy(src, dst):
        # at the moment of the rename the original must still be intact and
        # parseable: that is the whole guarantee
        seen["before"] = json.loads(Path(dst).read_text(encoding="utf-8"))
        return real_replace(src, dst)

    monkeypatch.setattr(config.os, "replace", spy)
    save_settings({"scan_interval_minutes": 30})

    assert seen["before"]["scan_interval_minutes"] == 15
    assert json.loads(path.read_text(encoding="utf-8"))["scan_interval_minutes"] == 30
    # and the temp file does not survive the save
    assert not path.with_name(f"{path.name}.tmp").exists()
