"""The receiving half of the Telegram inline buttons: one long poll, and the
curation each press applies.

**No webhook, deliberately.** Telegram delivers a button press one of two ways:
it POSTs to a public HTTPS endpoint, or it hands the press to whoever asks for
it. A webhook would mean an inbound port open on an API whose access control
*is* the loopback bind (invariant 14) — the one thing this project has refused
to trade away. So this module asks instead: a single background thread holding a
`getUpdates` long poll, outbound only, no port, no change to the network model.
The cost is one idle HTTPS connection; the alternative was a public attack
surface in front of an unauthenticated API.

**The actions do not reimplement curation.** A press is dispatched through
`routers.properties.bulk_properties` — the same entry point the dashboard's own
buttons use — so "hide" and "favourite" mean on the phone exactly what they mean
on screen, and invariants 5 (hidden is sacred, a scan never reverts it) and 10
(curated fields are only ever changed by the user) keep holding in one place
instead of two. The import is local to the call for the same reason the routers
import services lazily: the module graph stays acyclic.

**"Seen" writes nothing, on purpose.** The dashboard has no server-side notion of
a seen property — its "New" badge is a per-device `localStorage` threshold
(`App.tsx`), not a column — so a button that persisted one would be inventing a
concept no screen can show, which is a feature of its own rather than part of
this one. It is a dismissal of the *message*: the actions are stripped
from the keyboard and the notification stops asking to be triaged.

**Only the configured chat may act.** A bot's username is discoverable, so anyone
can open a chat with it. Telegram strips callback buttons from a forwarded
message, so the realistic exposure is small, but the check is what keeps that a
property of Telegram's behaviour rather than of this code.
"""

import logging
import threading

from sqlalchemy.orm import Session

from .. import schemas
from ..config import load_settings
from ..database import SessionLocal
from ..models import Property
from . import notifier

logger = logging.getLogger(__name__)

# Telegram holds the request open until an update arrives or this many seconds
# pass, so the poll costs one connection rather than a request per interval.
POLL_TIMEOUT_SECONDS = 25
# The read timeout has to outlast the long poll itself, or every quiet cycle
# would look like a network failure.
_READ_TIMEOUT_SECONDS = POLL_TIMEOUT_SECONDS + 10
# After a refused or unreachable API, wait before asking again: a token typo
# would otherwise spin a tight loop against api.telegram.org.
_ERROR_BACKOFF_SECONDS = 15
# How often the idle thread re-reads the settings, so enabling Telegram (or
# pasting a token) starts the poll without restarting the backend.
_IDLE_RECHECK_SECONDS = 30

_thread: threading.Thread | None = None
_stop = threading.Event()


def actions_configured(settings: dict | None = None) -> bool:
    """Whether button presses can be collected at all: the feature is on, and
    Telegram itself is configured. `telegram_chat_id` counts because it is the
    authorisation check — with no chat to compare against, every press would
    have to be refused anyway."""
    s = settings if settings is not None else load_settings()
    return bool(
        s.get("telegram_actions_enabled", True)
        and s.get("telegram_enabled")
        and (s.get("telegram_bot_token") or "").strip()
        and str(s.get("telegram_chat_id") or "").strip()
    )


def parse_callback_data(data: str | None) -> tuple[str, int] | None:
    """Splits "hide:42" into ("hide", 42), or None if it is not ours.

    Anything unrecognised is refused rather than guessed: the same bot may one
    day carry other buttons, and an id that is not a plain integer has no row
    behind it.
    """
    action, _, raw_id = (data or "").partition(notifier.CALLBACK_SEPARATOR)
    if action not in notifier.CALLBACK_ACTIONS or not raw_id.isdigit():
        return None
    return action, int(raw_id)


def apply_action(db: Session, action: str, property_id: int) -> tuple[str, Property | None]:
    """Applies one press and returns (toast text, the updated property).

    Favourite and Hide are toggles reading the row's current state, so a mis-tap
    is undone by tapping again — the notification is often the only surface the
    user has in hand, and a one-way Hide would send them to the dashboard to
    correct a fat finger. Both go through the shared bulk route, so "restore"
    here is the same restore the grid performs.
    """
    prop = db.get(Property, property_id)
    if prop is None:
        # Physical deletion only happens when a search is deleted with its
        # results (invariant 20); an old notification can outlive that.
        return "That property is no longer in the dashboard.", None

    if action == "seen":
        return "Marked as seen.", prop

    if action == "fav":
        bulk_action = "unfavorite" if prop.is_favorite else "favorite"
        text = "Removed from favourites." if prop.is_favorite else "Added to favourites."
    else:  # "hide"
        bulk_action = "restore" if prop.status == "hidden" else "hide"
        text = "Restored to the dashboard." if prop.status == "hidden" else "Hidden."

    from ..routers.properties import bulk_properties

    bulk_properties(schemas.PropertyBulkIn(ids=[property_id], action=bulk_action), db)
    db.refresh(prop)
    return text, prop


def _answer(callback_id: str, text: str) -> None:
    """Closes the press. Without this the button spins in the client until it
    times out, which reads as "the app is broken" even when the action landed."""
    if callback_id:
        notifier.telegram_api(
            "answerCallbackQuery", {"callback_query_id": callback_id, "text": text}
        )


def _redraw(message: dict, prop: Property | None, *, seen: bool) -> None:
    """Edits the keyboard so the message still describes the property's state.

    A "⭐ Favourite" button left in place on an already-favourited property is a
    message that has quietly started lying, and the notification often outlives
    the session that acted on it.
    """
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return
    if prop is None:
        markup: dict = {"inline_keyboard": []}
    elif seen:
        # Dismissed: the actions go, the map link stays useful.
        url = notifier.map_url(prop)
        markup = {"inline_keyboard": [[{"text": "🗺️ Map", "url": url}]] if url else []}
    else:
        markup = notifier.property_keyboard(prop) or {"inline_keyboard": []}
    notifier.telegram_api(
        "editMessageReplyMarkup",
        {"chat_id": chat_id, "message_id": message_id, "reply_markup": markup},
    )


def handle_callback(callback: dict, db: Session) -> str:
    """Handles one `callback_query`. Returns what it did, for the log and tests."""
    callback_id = str(callback.get("id") or "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    configured = str(load_settings().get("telegram_chat_id") or "").strip()
    if not configured or chat_id != configured:
        _answer(callback_id, "This bot only takes actions from its own chat.")
        return "unauthorized"

    parsed = parse_callback_data(callback.get("data"))
    if parsed is None:
        _answer(callback_id, "Unknown action.")
        return "unknown"

    action, property_id = parsed
    text, prop = apply_action(db, action, property_id)
    _answer(callback_id, text)
    _redraw(message, prop, seen=action == "seen")
    return action


def _drain(offset: int | None) -> int:
    """Confirms whatever is already queued without acting on it, and returns the
    offset to poll from.

    A press made while the backend was down would otherwise be replayed at
    startup: harmless for a toggle, wrong for the user, and genuinely surprising
    hours later. `offset=-1` asks for the last update alone; confirming past it
    discards the rest.
    """
    updates = notifier.telegram_api("getUpdates", {"offset": -1, "timeout": 0})
    if isinstance(updates, list) and updates:
        return int(updates[-1].get("update_id", 0)) + 1
    # Unreachable at startup: poll from wherever Telegram starts us. The replay
    # this guards against is rarer than losing the feature until a restart.
    return offset or 0


def _handle_update(update: dict) -> None:
    callback = update.get("callback_query")
    if not callback:
        return
    db = SessionLocal()
    try:
        logger.info("Telegram: button press -> %s", handle_callback(callback, db))
    finally:
        db.close()


def _loop() -> None:
    """One thread for the process lifetime, idling when Telegram is off.

    Re-reading the settings each pass is what lets the user enable the feature
    (or paste a new token) and have it work without restarting the backend —
    and it is why there is never a second poller: two consumers of the same
    token split the updates between them at random, so a "restart the thread on
    settings change" design would drop presses on the floor for as long as the
    old thread took to notice.
    """
    offset: int | None = None
    polled_token = ""
    while not _stop.is_set():
        settings = load_settings()
        if not actions_configured(settings):
            offset, polled_token = None, ""
            _stop.wait(_IDLE_RECHECK_SECONDS)
            continue

        token = (settings.get("telegram_bot_token") or "").strip()
        if token != polled_token:
            # Offsets are per-bot: a new token starts a new update stream.
            polled_token, offset = token, None
        if offset is None:
            offset = _drain(offset)

        updates = notifier.telegram_api(
            "getUpdates",
            {
                "offset": offset,
                "timeout": POLL_TIMEOUT_SECONDS,
                # Ask for presses alone: the bot has no reason to receive — or
                # to be able to read — the messages in the chat.
                "allowed_updates": ["callback_query"],
            },
            timeout=_READ_TIMEOUT_SECONDS,
        )
        if not isinstance(updates, list):
            _stop.wait(_ERROR_BACKOFF_SECONDS)
            continue

        for update in updates:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            try:
                _handle_update(update)
            except Exception:
                # One malformed press must not end the poll for the session.
                logger.exception("Telegram: failed to handle an update")


def start_polling() -> bool:
    """Starts the poll thread. Returns whether it started one.

    Called unconditionally at startup: the thread idles cheaply when Telegram is
    off, and starting it always is what makes enabling the feature take effect
    without a restart.
    """
    global _thread
    if _thread is not None and _thread.is_alive():
        return False
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="telegram-poll", daemon=True)
    _thread.start()
    logger.info("Telegram: button poll started")
    return True


def stop_polling() -> None:
    """Signals the thread to finish its current poll and exit.

    Deliberately does not join: the thread may be parked in a 25-second long
    poll, and blocking shutdown on it would stall every restart by that long.
    It is a daemon, so the interpreter does not wait for it either.
    """
    _stop.set()
