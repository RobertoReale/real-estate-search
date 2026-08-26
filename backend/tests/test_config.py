"""Tests for the settings file's compatibility with its own past versions.

A settings.json on a user's disk outlives the code that wrote it. When a
feature is removed its keys stay in that file, and the app has to keep reading
it — an unknown key must be inert, never an error, or removing a feature would
break every installation that had ever configured it.
"""

import json
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
