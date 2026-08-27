"""Tests for the Telegram inline buttons (PLAN 6.2): the keyboard a property
notification carries, and what a press does when it comes back.

Endpoint/handler functions are called directly (like test_tags), so the app
lifespan never starts and no poll thread is ever created — the network is only
ever reached through `notifier.telegram_api`, which every test here replaces.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.database import Base
from app.models import Property
from app.services import notifier, telegram_bot

CHAT_ID = "555000"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def telegram_configured():
    """A configured bot, written to the throwaway settings file conftest points
    every test at (invariant 17 — never the developer's real settings.json)."""
    config.save_settings(
        {
            "telegram_enabled": True,
            "telegram_bot_token": "123456:TESTTOKEN",
            "telegram_chat_id": CHAT_ID,
        }
    )


@pytest.fixture
def api_calls(monkeypatch):
    """Records every Bot API call instead of making it."""
    calls: list[tuple[str, dict]] = []

    def fake(method, payload, timeout=15):
        calls.append((method, payload))
        return {}

    monkeypatch.setattr(notifier, "telegram_api", fake)
    return calls


def make_property(db, **kw) -> Property:
    prop = Property(
        fingerprint=kw.pop("fingerprint", "fp-1"), title="Nice flat", city="Milano", **kw
    )
    db.add(prop)
    db.commit()
    return prop


def press(prop_id: int, action: str, chat_id: str = CHAT_ID) -> dict:
    """A callback_query as Telegram delivers it."""
    return {
        "id": "cb-1",
        "data": f"{action}{notifier.CALLBACK_SEPARATOR}{prop_id}",
        "message": {"message_id": 77, "chat": {"id": int(chat_id)}},
    }


# --- The keyboard ------------------------------------------------------------


def test_keyboard_carries_the_four_actions(db, telegram_configured):
    prop = make_property(db, latitude=45.46, longitude=9.19)
    markup = notifier.property_keyboard(prop)
    assert markup is not None
    labels = [b["text"] for row in markup["inline_keyboard"] for b in row]
    assert labels == ["⭐ Favourite", "👁️ Seen", "🚫 Hide", "🗺️ Map"]


def test_map_button_is_dropped_without_coordinates(db, telegram_configured):
    """A property with no pin cannot be placed on a map, so the button that
    would open one is omitted rather than pointing at the middle of nowhere —
    the same asymmetry invariant 19 makes visible in the map view."""
    prop = make_property(db)
    markup = notifier.property_keyboard(prop)
    assert markup is not None
    labels = [b["text"] for row in markup["inline_keyboard"] for b in row]
    assert "🗺️ Map" not in labels
    assert notifier.map_url(prop) == ""


def test_map_button_points_at_openstreetmap(db, telegram_configured):
    """Not at this app's own map view: the dashboard answers on the loopback
    bind (invariant 14), so such a link would be dead on the phone reading the
    notification."""
    prop = make_property(db, latitude=45.46, longitude=9.19)
    url = notifier.map_url(prop)
    assert url.startswith("https://www.openstreetmap.org/")
    assert "mlat=45.46" in url and "mlon=9.19" in url


def test_keyboard_labels_follow_the_stored_state(db, telegram_configured):
    """A message outlives the session that acted on it, so the buttons have to
    describe the property as it is now, not as it was when it was sent."""
    prop = make_property(db, is_favorite=True, status="hidden")
    markup = notifier.property_keyboard(prop)
    assert markup is not None
    labels = [b["text"] for row in markup["inline_keyboard"] for b in row]
    assert "⭐ Favourited" in labels
    assert "↩️ Restore" in labels


def test_no_keyboard_when_the_feature_is_off(db, telegram_configured):
    config.save_settings({"telegram_actions_enabled": False})
    prop = make_property(db, latitude=45.46, longitude=9.19)
    assert notifier.property_keyboard(prop) is None


def test_no_keyboard_for_an_unsaved_property(telegram_configured):
    """A callback naming no row could only ever answer "not found"."""
    assert notifier.property_keyboard(Property(fingerprint="unsaved")) is None


def test_a_new_property_notification_carries_the_keyboard(db, telegram_configured, monkeypatch):
    sent: list[dict | None] = []
    monkeypatch.setattr(
        notifier,
        "send_telegram_message",
        lambda text, reply_markup=None: sent.append(reply_markup) or True,
    )
    monkeypatch.setattr(notifier, "send_email_message", lambda text, subject=None: True)
    prop = make_property(db, latitude=45.46, longitude=9.19)

    notifier.notify_new_property(prop, ["telegram"])
    assert sent and sent[0] is not None
    assert sent[0]["inline_keyboard"][0][0]["callback_data"] == f"fav:{prop.id}"


# --- Parsing -----------------------------------------------------------------


def test_parse_callback_data_accepts_only_its_own_shape():
    assert telegram_bot.parse_callback_data("hide:42") == ("hide", 42)
    assert telegram_bot.parse_callback_data("fav:1") == ("fav", 1)
    assert telegram_bot.parse_callback_data("seen:1") == ("seen", 1)
    # not ours, malformed, or an id with no row behind it
    assert telegram_bot.parse_callback_data("delete:1") is None
    assert telegram_bot.parse_callback_data("hide:abc") is None
    assert telegram_bot.parse_callback_data("hide:") is None
    assert telegram_bot.parse_callback_data("") is None
    assert telegram_bot.parse_callback_data(None) is None


# --- What a press does -------------------------------------------------------


def test_favourite_toggles_and_hide_toggles(db, telegram_configured, api_calls):
    """Both are toggles: the notification is often the only surface in hand, and
    a one-way Hide would send the user to the dashboard to undo a mis-tap."""
    prop = make_property(db)

    assert telegram_bot.handle_callback(press(prop.id, "fav"), db) == "fav"
    assert db.get(Property, prop.id).is_favorite is True
    telegram_bot.handle_callback(press(prop.id, "fav"), db)
    assert db.get(Property, prop.id).is_favorite is False

    telegram_bot.handle_callback(press(prop.id, "hide"), db)
    assert db.get(Property, prop.id).status == "hidden"
    telegram_bot.handle_callback(press(prop.id, "hide"), db)
    assert db.get(Property, prop.id).status == "active"


def test_seen_acknowledges_without_touching_the_database(db, telegram_configured, api_calls):
    """There is no server-side "seen" concept — the dashboard's New badge is a
    per-device localStorage threshold — so this dismisses the message and
    persists nothing. Invariant 10: curated fields change only when the user
    asks for that change."""
    prop = make_property(db, is_favorite=True)

    assert telegram_bot.handle_callback(press(prop.id, "seen"), db) == "seen"
    after = db.get(Property, prop.id)
    assert after.is_favorite is True
    assert after.status == "active"
    # the actions are stripped from the message, so it stops asking to be triaged
    edits = [p for method, p in api_calls if method == "editMessageReplyMarkup"]
    assert edits and edits[-1]["reply_markup"] == {"inline_keyboard": []}


def test_a_press_from_another_chat_changes_nothing(db, telegram_configured, api_calls):
    """A bot's username is discoverable, so anyone can open a chat with it."""
    prop = make_property(db)

    assert telegram_bot.handle_callback(press(prop.id, "hide", chat_id="999"), db) == "unauthorized"
    assert db.get(Property, prop.id).status == "active"
    assert not [m for m, _ in api_calls if m == "editMessageReplyMarkup"]


def test_a_press_on_a_deleted_property_is_answered_not_raised(db, telegram_configured, api_calls):
    """Deleting a search with its results physically removes properties
    (invariant 20), and an old notification can outlive that."""
    assert telegram_bot.handle_callback(press(4242, "hide"), db) == "hide"
    answers = [p for method, p in api_calls if method == "answerCallbackQuery"]
    assert answers and "no longer in the dashboard" in answers[-1]["text"]


def test_every_press_is_answered(db, telegram_configured, api_calls):
    """Without answerCallbackQuery the button spins in the client until it times
    out, which reads as a broken app even when the action landed."""
    prop = make_property(db)
    for action in ("fav", "seen", "hide"):
        api_calls.clear()
        telegram_bot.handle_callback(press(prop.id, action), db)
        assert [m for m, _ in api_calls if m == "answerCallbackQuery"]


def test_the_keyboard_is_redrawn_after_an_action(db, telegram_configured, api_calls):
    prop = make_property(db)
    telegram_bot.handle_callback(press(prop.id, "fav"), db)
    edits = [p for method, p in api_calls if method == "editMessageReplyMarkup"]
    assert edits
    labels = [b["text"] for row in edits[-1]["reply_markup"]["inline_keyboard"] for b in row]
    assert "⭐ Favourited" in labels


# --- Gating ------------------------------------------------------------------


def test_actions_configured_needs_the_whole_set(telegram_configured):
    assert telegram_bot.actions_configured() is True
    # the chat id is the authorisation check: without one every press would
    # have to be refused anyway
    config.save_settings({"telegram_chat_id": ""})
    assert telegram_bot.actions_configured() is False
    config.save_settings({"telegram_chat_id": CHAT_ID, "telegram_actions_enabled": False})
    assert telegram_bot.actions_configured() is False


def test_actions_are_off_when_telegram_is(telegram_configured):
    config.save_settings({"telegram_enabled": False})
    assert telegram_bot.actions_configured() is False
