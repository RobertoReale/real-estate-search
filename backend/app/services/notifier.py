"""Multi-channel notifications: Telegram (Bot API) and Email (SMTP).

Channel architecture: every notification is composed once as simple HTML
(Telegram's subset: <b>, <a>) and broadcast to the requested channels.
A profile can restrict its own channels via SearchProfile.notify_channels
(comma-separated, e.g. "email"); empty means "all enabled channels".

Telegram uses the raw Bot API (no external library); email uses stdlib
smtplib so no new dependencies are required.
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


def send_telegram_message(text: str) -> bool:
    settings = load_settings()
    token = settings.get("telegram_bot_token")
    chat_id = settings.get("telegram_chat_id")
    if not settings.get("telegram_enabled") or not token or not chat_id:
        return False
    try:
        resp = curl_requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        ok = resp.status_code == 200 and resp.json().get("ok", False)
        if not ok:
            logger.warning("Telegram: send failed: %s", resp.text[:300])
        return ok
    except Exception:
        logger.exception("Telegram: network error during send")
        return False


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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    plain = re.sub(r"<[^>]+>", "", text)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(
        f'<div style="font-family:sans-serif;font-size:14px;white-space:pre-line">'
        f"{text}</div>",
        "html", "utf-8",
    ))

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
    return [c.strip().lower() for c in (csv or "").split(",")
            if c.strip().lower() in CHANNELS]


def broadcast(text: str, channels: list[str] | None = None,
              subject: str | None = None) -> bool:
    """Sends to every requested channel; empty/None = all channels.

    Whether a channel actually fires still depends on its own "enabled"
    setting, so a profile requesting "email" while email is off sends nothing.
    Returns True if at least one channel delivered.
    """
    targets = channels or list(CHANNELS)
    sent = False
    if "telegram" in targets:
        sent = send_telegram_message(text) or sent
    if "email" in targets:
        sent = send_email_message(text, subject=subject) or sent
    return sent


def _fmt_price(value: float | None, contract: str = "sale") -> str:
    if not value:
        return "N/A"
    formatted = f"{value:,.0f} €".replace(",", ".")
    return f"{formatted}/month" if contract == "rent" else formatted


def notify_new_property(prop: Property, channels: list[str] | None = None) -> bool:
    portals = ", ".join(sorted({l.portal for l in prop.listings}))
    url = prop.listings[0].url if prop.listings else ""
    sqm_part = f" · {prop.sqm:.0f} sqm" if prop.sqm else ""
    rooms_part = f" · {prop.rooms} rooms" if prop.rooms else ""
    price_sqm = (
        f"\n📐 {prop.current_min_price / prop.sqm:,.0f} €/sqm".replace(",", ".")
        if prop.current_min_price and prop.sqm else ""
    )
    label = "New rental" if prop.contract == "rent" else "New property"
    text = (
        f"🏠 <b>{label}</b>\n"
        f"{html.escape(prop.title or 'Untitled')}\n"
        f"📍 {html.escape(prop.city or '?')} {html.escape(prop.zone or '')}"
        f"{sqm_part}{rooms_part}\n"
        f"💰 <b>{_fmt_price(prop.current_min_price, prop.contract)}</b>{price_sqm}\n"
        f"🌐 Sources: {portals}\n"
        f'<a href="{html.escape(url)}">Open listing</a>'
    )
    subject = f"🏠 {label}: {prop.title or prop.city or 'listing'}"
    return broadcast(text, channels, subject=subject)


def notify_price_drop(prop: Property, old_price: float, new_price: float,
                      channels: list[str] | None = None) -> bool:
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
    return broadcast(text, channels, subject=subject)


def notify_scraper_failure(profile: SearchProfile, failures: int,
                           channels: list[str] | None = None) -> bool:
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
    text = (
        f"🚨 <b>Scraper health alert</b>\n"
        f"Search <b>{html.escape(profile.name)}</b> ({profile.portal}) has "
        f"failed <b>{failures}</b> consecutive scans: {reason}.{detail}\n"
        f"New listings from this search are not reaching you."
    )
    subject = f"🚨 Scraper failing: {profile.name}"
    return broadcast(text, channels, subject=subject)


def notify_scraper_recovered(profile: SearchProfile, failures: int,
                             channels: list[str] | None = None) -> bool:
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
