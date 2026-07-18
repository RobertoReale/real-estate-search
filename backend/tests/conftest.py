"""Fixtures shared by the whole suite.

The tests are meant to be offline and reproducible, but `load_settings()` reads
`backend/settings.json` from disk — so the moment a developer configured real
Gmail credentials there, `test_disabled_channels_send_nothing` stopped testing
"disabled channels": it logged into smtp.gmail.com and delivered an actual
email. Point every test at an empty settings file so the defaults apply and no
real credential is ever reachable from a test run.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
