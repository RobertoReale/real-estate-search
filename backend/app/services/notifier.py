"""Multi-channel notifications: Telegram (Bot API) and Email (SMTP).

Channel architecture: every notification is composed once as simple HTML
(Telegram's subset: <b>, <a>) and broadcast to the requested channels.
A profile can restrict its own channels via SearchProfile.notify_channels
(comma-separated, e.g. "email"); empty means "all enabled channels" and the
MUTED sentinel means "no notification at all for this search".

Telegram uses the raw Bot API (no external library); email uses stdlib
smtplib so no new dependencies are required.

A property notification also carries the inline keyboard built here
(`property_keyboard`): composing the buttons is part of composing the message.
Collecting the *presses* is the other half and lives in `telegram_bot.py`,
which imports this module — the dependency runs one way only, so the builder
that draws a keyboard and the handler that redraws it after an action stay the
same function.
"""

import html
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from curl_cffi import requests as curl_requests

from ..config import load_settings
from ..models import Property, SearchProfile

logger = logging.getLogger(__name__)

CHANNELS = ("telegram", "email")
# `notify_channels` value meaning "this search notifies nowhere". Not a channel:
# it is the absence of every channel, kept out of CHANNELS on purpose.
MUTED = "none"


def telegram_api(method: str, payload: dict, timeout: int = 15) -> dict | list | None:
    """Calls one Bot API method and returns its `result`, or None on any failure.

    The single place that knows the endpoint shape, so sending a message and
    polling for button presses cannot drift apart. Fail-open like the rest of
    the optional paths: a network error, a refused token or an `ok: false` body
    is logged and answered with None — a notification that cannot be delivered
    must never take a scan down with it.
    """
    token = (load_settings().get("telegram_bot_token") or "").strip()
    if not token:
        return None
    try:
        resp = curl_requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
            timeout=timeout,
        )
        body = resp.json() if resp.status_code == 200 else {}
        if not body.get("ok"):
            logger.warning("Telegram: %s failed: %s", method, resp.text[:300])
            return None
        return body.get("result")
    except Exception:
        logger.exception("Telegram: network error during %s", method)
        return None


def send_telegram_message(text: str, reply_markup: dict | None = None) -> bool:
    settings = load_settings()
    if not settings.get("telegram_enabled") or not settings.get("telegram_chat_id"):
        return False
    payload = {
        "chat_id": settings["telegram_chat_id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api("sendMessage", payload) is not None


def send_email_message(text: str, subject: str | None = None) -> bool:
    """Sends the notification as an HTML email via the configured SMTP server."""
    settings = load_settings()
    if not settings.get("email_enabled"):
        return False
    host = settings.get("smtp_host")
    to_addr = settings.get("email_to")
    if not host or not to_addr:
        return False
    from_addr = settings.get("email_from") or settings.get("smtp_user") or to_addr

    if subject is None:
        # first line of the message, stripped of tags, works as a subject
        subject = re.sub(r"<[^>]+>", "", text.splitlines()[0]).strip() or "Notification"
    # subjects carry scraped titles (untrusted): a newline in one would smuggle
    # extra headers into the message (header injection under compat32)
    subject = re.sub(r"[\r\n]+", " ", subject).strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    plain = re.sub(r"<[^>]+>", "", text)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(
        MIMEText(
            f'<div style="font-family:sans-serif;font-size:14px;white-space:pre-line">{text}</div>',
            "html",
            "utf-8",
        )
    )

    try:
        port = int(settings.get("smtp_port") or 587)
        user = settings.get("smtp_user") or ""
        password = settings.get("smtp_password") or ""
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
        with server:
            if port != 465:
                # STARTTLS is standard on 587; harmless to skip if unsupported
                try:
                    server.starttls()
                except smtplib.SMTPNotSupportedError:
                    pass
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception:
        logger.exception("Email: send failed")
        return False


def parse_channels_csv(csv: str) -> list[str]:
    return [c.strip().lower() for c in (csv or "").split(",") if c.strip().lower() in CHANNELS]


def profile_channels(csv: str) -> list[str] | None:
    """Resolves a profile's `notify_channels` into what broadcast() expects.

    Three states, and the empty string cannot express all three: "" means "all
    enabled channels" (the default), a CSV means those channels, and the MUTED
    sentinel means this search notifies nothing at all — the user wants it on
    the dashboard but silent. Hence `None` (= all) vs `[]` (= muted), which
    parse_channels_csv alone could not distinguish.
    """
    if (csv or "").strip().lower() == MUTED:
        return []
    return parse_channels_csv(csv) or None


def broadcast(
    text: str,
    channels: list[str] | None = None,
    subject: str | None = None,
    reply_markup: dict | None = None,
) -> bool:
    """Sends to every requested channel; None = all channels, [] = none.

    Whether a channel actually fires still depends on its own "enabled"
    setting, so a profile requesting "email" while email is off sends nothing.
    Returns True if at least one channel delivered. `reply_markup` is Telegram's
    alone — email has no buttons, and the same message body reads correctly in
    both, which is why the actions are attached rather than written into it.
    """
    # an empty list is a muted profile, not "unspecified": `channels or CHANNELS`
    # would silently turn the mute into a broadcast to everything
    targets = list(CHANNELS) if channels is None else channels
    sent = False
    if "telegram" in targets:
        sent = send_telegram_message(text, reply_markup=reply_markup) or sent
    if "email" in targets:
        sent = send_email_message(text, subject=subject) or sent
    return sent


# Telegram caps callback_data at 64 bytes, so it carries the action and the id
# and nothing else; everything the handler needs beyond that it reads from the
# database. The separator cannot occur in either half (actions are literals,
# ids are digits), so `partition` is an unambiguous parse.
CALLBACK_SEPARATOR = ":"
CALLBACK_ACTIONS = ("fav", "seen", "hide")


def map_url(prop: Property) -> str:
    """An OpenStreetMap pin for the property, or "" when it has no coordinates.

    Deliberately not a link into this app's own map view: the dashboard answers
    on the loopback bind (invariant 14), so a `http://127.0.0.1:8000` button
    would be dead on the phone that is showing the notification. OSM is
    reachable from wherever Telegram is, and it is the same map background
    `MapView` draws.
    """
    if prop.latitude is None or prop.longitude is None:
        return ""
    lat, lng = prop.latitude, prop.longitude
    return f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}"


def property_keyboard(prop: Property) -> dict | None:
    """The inline keyboard a property notification carries, or None for no
    buttons at all (`telegram_actions_enabled` off, or an unsaved property —
    a button whose callback names no row could only ever answer "not found").

    Favourite and Hide render the state they would *leave*, so the message keeps
    telling the truth after a press: `telegram_bot` rebuilds this keyboard from
    the updated row and edits it back onto the message.
    """
    if not load_settings().get("telegram_actions_enabled", True) or not prop.id:
        return None
    sep = CALLBACK_SEPARATOR
    actions = [
        {
            "text": "⭐ Favourited" if prop.is_favorite else "⭐ Favourite",
            "callback_data": f"fav{sep}{prop.id}",
        },
        {"text": "👁️ Seen", "callback_data": f"seen{sep}{prop.id}"},
        {
            "text": "↩️ Restore" if prop.status == "hidden" else "🚫 Hide",
            "callback_data": f"hide{sep}{prop.id}",
        },
    ]
    url = map_url(prop)
    link_row = [{"text": "🗺️ Map", "url": url}] if url else []
    return {"inline_keyboard": [actions] + ([link_row] if link_row else [])}


def _fmt_price(value: float | None, contract: str = "sale") -> str:
    if not value:
        return "N/A"
    formatted = f"{value:,.0f} €".replace(",", ".")
    return f"{formatted}/month" if contract == "rent" else formatted


def _deal_line(prop: Property) -> str:
    """A "below market" highlight for an undervalued listing, or "" otherwise.

    Reads the transient Deal Score fields (services/deal_score); when the scan
    did not annotate them, or the listing is not undervalued, the notification
    stays exactly as it was — the flag is opt-in signal, never noise."""
    score = getattr(prop, "deal_score", None)
    if score is None or getattr(prop, "deal_label", None) != "undervalued":
        return ""
    low = getattr(prop, "target_price_low", None)
    high = getattr(prop, "target_price_high", None)
    target = ""
    if low and high:
        target = f" · Target {_fmt_price(low, prop.contract)}–{_fmt_price(high, prop.contract)}"
    return f"\n🎯 <b>Below market ({score:+d}%)</b>{target}"


def notify_new_property(prop: Property, channels: list[str] | None = None) -> bool:
    portals = ", ".join(sorted({l.portal for l in prop.listings}))
    url = prop.listings[0].url if prop.listings else ""
    sqm_part = f" · {prop.sqm:.0f} sqm" if prop.sqm else ""
    rooms_part = f" · {prop.rooms} rooms" if prop.rooms else ""
    price_sqm = (
        f"\n📐 {prop.current_min_price / prop.sqm:,.0f} €/sqm".replace(",", ".")
        if prop.current_min_price and prop.sqm
        else ""
    )
    label = "New rental" if prop.contract == "rent" else "New property"
    text = (
        f"🏠 <b>{label}</b>\n"
        f"{html.escape(prop.title or 'Untitled')}\n"
        f"📍 {html.escape(prop.city or '?')} {html.escape(prop.zone or '')}"
        f"{sqm_part}{rooms_part}\n"
        f"💰 <b>{_fmt_price(prop.current_min_price, prop.contract)}</b>{price_sqm}"
        f"{_deal_line(prop)}\n"
        f"🌐 Sources: {portals}\n"
        f'<a href="{html.escape(url)}">Open listing</a>'
    )
    subject = f"🏠 {label}: {prop.title or prop.city or 'listing'}"
    return broadcast(text, channels, subject=subject, reply_markup=property_keyboard(prop))


def notify_price_drop(
    prop: Property, old_price: float, new_price: float, channels: list[str] | None = None
) -> bool:
    pct = (new_price - old_price) / old_price * 100 if old_price else 0
    url = prop.listings[0].url if prop.listings else ""
    text = (
        f"📉 <b>Price changed ({pct:+.1f}%)</b>\n"
        f"{html.escape(prop.title or 'Untitled')}\n"
        f"📍 {html.escape(prop.city or '?')}\n"
        f"💰 {_fmt_price(old_price, prop.contract)} → "
        f"<b>{_fmt_price(new_price, prop.contract)}</b>\n"
        f'<a href="{html.escape(url)}">Open listing</a>'
    )
    subject = f"📉 Price change ({pct:+.1f}%): {prop.title or prop.city or 'listing'}"
    return broadcast(text, channels, subject=subject, reply_markup=property_keyboard(prop))


def notify_property_reactivated(
    prop: Property, previous_status: str, channels: list[str] | None = None
) -> bool:
    """A property that left the visible market came back: "gone" reappeared on
    the portal, or "filtered" no longer matches an exclusion keyword. Without
    this the transition happened silently, and a returned listing is exactly
    as actionable as a new one."""
    reason = (
        "back on the market" if previous_status == "gone" else "no longer excluded by your keywords"
    )
    url = prop.listings[0].url if prop.listings else ""
    text = (
        f"🔄 <b>Property {reason}</b>\n"
        f"{html.escape(prop.title or 'Untitled')}\n"
        f"📍 {html.escape(prop.city or '?')} {html.escape(prop.zone or '')}\n"
        f"💰 <b>{_fmt_price(prop.current_min_price, prop.contract)}</b>\n"
        f'<a href="{html.escape(url)}">Open listing</a>'
    )
    subject = f"🔄 Back on the market: {prop.title or prop.city or 'listing'}"
    return broadcast(text, channels, subject=subject, reply_markup=property_keyboard(prop))


def notify_scraper_failure(
    profile: SearchProfile, failures: int, channels: list[str] | None = None
) -> bool:
    """Warns that a search has stopped producing listings.

    A broken scraper is silent by nature: no listings means no notifications,
    which is indistinguishable from "the market is quiet". This is the only
    message that says "you are no longer being told about new properties".
    """
    reason = (
        "the portal is blocking the scraper (anti-bot)"
        if profile.last_run_status == "blocked"
        else "the scraper is failing with an error"
    )
    detail = f"\n<i>{html.escape(profile.last_run_detail)}</i>" if profile.last_run_detail else ""
    # say WHY in transport terms (plan B.5): the alert is more actionable when
    # it states which rungs of the ladder were available and what to add next
    from ..config import load_settings

    try:
        settings = load_settings()
        from ..scrapers.transport import ProxyPool

        levers = []
        if not ProxyPool.configured_proxies(settings):
            levers.append("a proxy pool")
        if not (settings.get("scrape_api_key") or "").strip():
            levers.append("a scrape-API key")
        advice = (
            f"\nAll configured transports were tried; consider adding {' or '.join(levers)}."
            if levers
            else ""
        )
    except Exception:
        advice = ""
    text = (
        f"🚨 <b>Scraper health alert</b>\n"
        f"Search <b>{html.escape(profile.name)}</b> ({profile.portal}) has "
        f"failed <b>{failures}</b> consecutive scans: {reason}.{detail}\n"
        f"New listings from this search are not reaching you.{advice}"
    )
    subject = f"🚨 Scraper failing: {profile.name}"
    return broadcast(text, channels, subject=subject)


def notify_scraper_recovered(
    profile: SearchProfile, failures: int, channels: list[str] | None = None
) -> bool:
    """Closes an outage the user was alerted about; sent only in that case,
    so it can never arrive without a preceding alert."""
    text = (
        f"✅ <b>Scraper recovered</b>\n"
        f"Search <b>{html.escape(profile.name)}</b> ({profile.portal}) is "
        f"working again after {failures} failed scans."
    )
    subject = f"✅ Scraper recovered: {profile.name}"
    return broadcast(text, channels, subject=subject)


def send_test_message(channel: str | None = None) -> bool:
    text = "✅ Test successful! The real estate bot is configured correctly."
    if channel == "telegram":
        return send_telegram_message(text)
    if channel == "email":
        return send_email_message(text, subject="✅ Real Estate Search — test")
    return broadcast(text)
