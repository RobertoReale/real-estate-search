"""Email inbox import: mines the user's mailbox for portal listing emails.

People who subscribed to Immobiliare.it / Idealista email alerts for years
have hundreds of listing notifications in their inbox. This module connects
via IMAP — **strictly read-only**: the mailbox is opened with
`select(readonly=True)` and messages are fetched with BODY.PEEK, so not even
the \\Seen flag is touched — extracts the listing links those emails contain,
and stages them as ImportedListing rows for the user to review.

Design constraints, in order of importance:
- Nothing enters the dashboard without an explicit "accept": alert emails are
  often years old and the data quality is whatever the email contained.
- Idempotent re-scans: a listing already tracked (Listing table), already
  staged, or already discarded is never staged twice. Discarded rows are the
  memory that keeps rejected listings from coming back.
- No listing page is fetched from the portals here: mass-visiting hundreds of
  old (mostly 404) ads would be slow and a DataDome ban magnet. The email
  body is the single source of data.
- A link the email said nothing about is not staged (`_has_details`): with no
  name, price, surface or rooms there is nothing to review, and since the ad
  page is never opened, a dead link looks exactly like a live one.

Like the scrapers, extraction never relies on CSS classes — only on the URL
patterns the portals cannot change without breaking their own links
(/annunci/<id>, /immobile/<id>), including their percent-encoded forms inside
click-tracking redirects.
"""
import email
import imaplib
import logging
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from urllib.parse import unquote

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import load_settings
from ..database import SessionLocal
from ..models import ImportedListing, Listing, Property, SearchProfile
from ..scrapers.base import AdProbe, RawListing, detect_contract, parse_price, \
    parse_rooms, parse_sqm
from .deduplicator import upsert_listing
from .filter_engine import parse_keywords_csv

logger = logging.getLogger(__name__)


class ImapError(Exception):
    """Connection/authentication/search failure, with a user-facing message."""


# Ad URL patterns in both raw and percent-encoded form: alert emails wrap
# every link in a click-tracking redirect that embeds the target URL encoded.
PORTAL_AD_RES: dict[str, re.Pattern] = {
    "immobiliare": re.compile(
        r"immobiliare\.it(?:/|%2F)annunci(?:/|%2F)(\d+)", re.IGNORECASE
    ),
    "idealista": re.compile(
        r"idealista\.it(?:/|%2F)immobile(?:/|%2F)(\d+)", re.IGNORECASE
    ),
}
CANONICAL_URL = {
    "immobiliare": "https://www.immobiliare.it/annunci/{id}/",
    "idealista": "https://www.idealista.it/immobile/{id}/",
}
# Idealista mails from @idealista.com; sender search is substring-based so
# "idealista.com" also covers no-reply subdomains.
PORTAL_SENDER_DOMAINS = ("immobiliare.it", "idealista.com", "idealista.it")

RENT_HINT_RE = re.compile(r"affitt|locazion|\brent", re.IGNORECASE)

# Anchor text that is not a title. Alert emails link the same ad from the photo,
# from a call-to-action button, and from a "if the link does not work, copy this
# address" footer — and that last one renders as a bare URL, which the review
# card would then show as the property's name. The Italian wording is
# deliberate: it must match what the portals actually write, exactly like
# DEFAULT_EXCLUDED_KEYWORDS.
_NON_TITLES = {
    "vedi l'annuncio", "vedi annuncio", "vai all'annuncio", "guarda l'annuncio",
    "scopri di piu", "scopri di più", "vedi di piu", "vedi di più",
    "clicca qui", "leggi tutto", "visualizza", "apri", "dettagli",
    "vedi tutti gli annunci", "vedi altri annunci",
    "view listing", "see more", "more details", "click here",
}
_URLISH_RE = re.compile(r"^(?:https?://|www\.)\S*$", re.IGNORECASE)


def _clean_title(text: str) -> str:
    """Anchor text reduced to a usable title, or "" when it carries no name."""
    title = " ".join((text or "").replace("’", "'").split())
    if not title or title.isdigit() or _URLISH_RE.match(title):
        return ""
    if title.casefold().strip(" .!:>›»→") in _NON_TITLES:
        return ""
    # Strip common agency and email alert boilerplate
    title = re.sub(r"^(?:Affiliato\s+[^:]+|Gabetti\s+[^:]+|TEMPOCASA\s+[^:]+|STUDIO\s+[^:]+|Strategie\s+Immobiliari\s*|Dhome\s+Real\s+Estate\s*|Cosetta\s+Fiori\s*):\s*", "", title, flags=re.I)
    title = re.sub(r"\b(?:ti propone un immobile per la tua ricerca\s*:?|ti propone\s*:?|\s+:\s+Residenziale in vendita)\s*", "", title, flags=re.I)
    title = re.sub(r"\s*\|\s*(?:Immobiliare\.it|Idealista|Casa\.it).*$", "", title, flags=re.I)
    title = " ".join(title.split()).strip(" :-")
    if not title or title.casefold() in ("residenziale in vendita a milano, milano", "in vendita a milano, milano", "vendita a milano, milano", "residenziale in vendita a milano"):
        return ""
    return title[:200]



def _has_details(entry: dict) -> bool:
    """Whether a link taught us anything at all about the property.

    A link with no name, no price, no surface and no room count is not a
    listing card: it is the footer's plain URL, or a tracking pixel's anchor.
    Staging it produces a review row reading "N/A · sale" that nobody can
    judge — and the ad behind it is often long gone, which is precisely the
    thing this panel cannot check without visiting the portal.
    """
    return bool(entry["title"]) or any(
        entry[f] is not None for f in ("price", "sqm", "rooms")
    )

# IMAP dates must use English month abbreviations regardless of the OS
# locale, so strftime("%b") is not an option.
_IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _imap_date(d: date) -> str:
    return f"{d.day:02d}-{_IMAP_MONTHS[d.month - 1]}-{d.year}"


def _connect(settings: dict) -> imaplib.IMAP4_SSL:
    host = (settings.get("imap_host") or "").strip()
    user = (settings.get("imap_user") or "").strip()
    password = settings.get("imap_password") or ""
    if not host or not user or not password:
        raise ImapError(
            "IMAP is not configured: set host, username and password in "
            "Settings (for Gmail: imap.gmail.com + an app password)"
        )
    try:
        client = imaplib.IMAP4_SSL(host, int(settings.get("imap_port") or 993))
        client.login(user, password)
    except (imaplib.IMAP4.error, OSError) as e:
        raise ImapError(f"IMAP connection failed: {e}") from e
    return client


def _logout(client) -> None:
    try:
        client.logout()
    except Exception:  # a broken logout must not mask the real result
        pass


def test_connection() -> dict:
    """Connects, opens INBOX read-only, and reports the message count."""
    client = _connect(load_settings())
    try:
        status, data = client.select("INBOX", readonly=True)
        if status != "OK":
            raise ImapError("Connected, but could not open INBOX")
        return {"ok": True,
                "detail": f"Connected — INBOX holds {int(data[0] or 0)} messages"}
    finally:
        _logout(client)


def _search_criteria(mode: str, senders: str, since_days: int) -> str:
    if mode == "portals":
        terms = [f'FROM "{d}"' for d in PORTAL_SENDER_DOMAINS]
    elif mode == "address":
        # quotes and backslashes cannot appear in an address anyway, but left
        # in they break out of the quoted IMAP string and abort the search
        addresses = [
            s.strip().replace('"', "").replace("\\", "")
            for s in (senders or "").split(",") if s.strip()
        ]
        addresses = [a for a in addresses if a]
        if not addresses:
            raise ImapError(
                "Searching by sender needs at least one email address or domain"
            )
        terms = [f'FROM "{a}"' for a in addresses]
    else:  # "any": every message that mentions the portals anywhere
        terms = [f'TEXT "{d}"' for d in ("immobiliare.it", "idealista.it")]
    # IMAP OR is a binary prefix operator: OR a OR b c == a | b | c
    criteria = terms[0]
    for term in terms[1:]:
        criteria = f"OR {term} {criteria}"
    since = _imap_date(date.today() - timedelta(days=since_days))
    return f"(SINCE {since} {criteria})"


# --- Message parsing ---------------------------------------------------------

def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, "replace")
    except LookupError:
        return payload.decode("utf-8", "replace")


def _message_bodies(msg: Message) -> tuple[list[str], list[str]]:
    """(html_parts, plain_parts), decoded."""
    htmls, plains = [], []
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/html":
            htmls.append(_part_text(part))
        elif content_type == "text/plain":
            plains.append(_part_text(part))
    return htmls, plains


def _match_portal(href: str) -> tuple[str, str] | None:
    """(portal, portal_id) if the href points to (or wraps) an ad page."""
    href = unquote(href or "")
    for portal, pattern in PORTAL_AD_RES.items():
        m = pattern.search(href)
        if m and m.group(1).strip("0"):  # /annunci/0/ is a template placeholder
            return portal, m.group(1)
    return None


def _extract_image_from_container(container, anchor) -> str:
    imgs = anchor.find_all("img", src=True) if hasattr(anchor, "find_all") else []
    if not imgs and hasattr(container, "find_all"):
        imgs = container.find_all("img", src=True)
    for img in imgs:
        src = str(img["src"]).strip()
        if not src or not src.lower().startswith(("http://", "https://")):
            continue
        src_lower = src.lower()
        if any(bad in src_lower for bad in (
            "logo", "pixel", "tracking", "tracker", "spacer", "1x1", "blank",
            "facebook", "twitter", "instagram", "linkedin", "apple", "google",
            "playstore", "appstore", "icon", "arrow", "social", "badge"
        )):
            continue
        width = img.get("width", "")
        height = img.get("height", "")
        try:
            if width and int(str(width).replace("px", "").strip()) <= 30:
                continue
            if height and int(str(height).replace("px", "").strip()) <= 30:
                continue
        except (ValueError, TypeError):
            pass
        return src[:500]
    return ""


def _merge_entry(found: dict, entry: dict) -> None:
    """Same ad linked N times per email (image + title + button): keep the
    richest combination of fields instead of the first occurrence."""
    key = (entry["portal"], entry["portal_id"])
    current = found.get(key)
    if current is None:
        found[key] = entry
        return
    if len(entry["title"]) > len(current["title"]):
        current["title"] = entry["title"]
    for f in ("price", "sqm", "rooms"):
        if current[f] is None and entry[f] is not None:
            current[f] = entry[f]
    if not current.get("image_url") and entry.get("image_url"):
        current["image_url"] = entry["image_url"]


def _extract_from_html(html_text: str, contract: str, found: dict) -> None:
    soup = BeautifulSoup(html_text, "html.parser")

    def ad_keys(node) -> set:
        keys = set()
        for a in node.find_all("a", href=True):
            hit = _match_portal(str(a["href"]))
            if hit:
                keys.add(hit)
        return keys

    for anchor in soup.find_all("a", href=True):
        hit = _match_portal(str(anchor["href"]))
        if not hit:
            continue
        portal, portal_id = hit
        # climb to the card boundary exactly like the scrapers do: the last
        # ancestor that still references only this ad. One level further up
        # is the mail's listing grid, where prices of *other* ads live.
        container = node = anchor
        for _ in range(8):
            parent = node.parent
            if parent is None or len(ad_keys(parent)) > 1:
                break
            container = node = parent
        text = container.get_text(" ", strip=True)
        title = _clean_title(anchor.get_text(" ", strip=True))
        if not title:
            img = anchor.find("img", alt=True)
            title = _clean_title(str(img["alt"])) if img else ""
        image_url = _extract_image_from_container(container, anchor)
        _merge_entry(found, {
            "portal": portal, "portal_id": portal_id,
            "title": title,
            "price": parse_price(text, contract),
            "sqm": parse_sqm(text),
            "rooms": parse_rooms(text),
            "image_url": image_url,
        })


def _extract_from_plain(text: str, contract: str, found: dict) -> None:
    for pattern in PORTAL_AD_RES.values():
        for m in pattern.finditer(unquote(text or "")):
            hit = _match_portal(m.group(0))
            if not hit:
                continue
            portal, portal_id = hit
            window = text[max(0, m.start() - 250):m.end() + 250]
            _merge_entry(found, {
                "portal": portal, "portal_id": portal_id,
                "title": "",
                "price": parse_price(window, contract),
                "sqm": parse_sqm(window),
                "rooms": parse_rooms(window),
            })


def extract_listings(raw_message: bytes) -> tuple[list[dict], dict]:
    """Parses one raw RFC822 message into (listing entries, email metadata)."""
    msg = email.message_from_bytes(raw_message)
    subject = str(make_header(decode_header(msg.get("Subject") or "")))
    sender = parseaddr(msg.get("From") or "")[1]
    try:
        email_date = parsedate_to_datetime(msg.get("Date") or "")
    except (TypeError, ValueError):
        email_date = None

    htmls, plains = _message_bodies(msg)
    # the contract is guessed from the email text — portal ad URLs do not
    # encode it (unlike search URLs). The user reviews it before accepting.
    contract = "rent" if RENT_HINT_RE.search(
        " ".join([subject, *plains]) or subject
    ) else "sale"

    found: dict = {}
    for html_text in htmls:
        _extract_from_html(html_text, contract, found)
    if not found:  # plain-only mails (or html without recognisable links)
        for plain in plains:
            _extract_from_plain(plain, contract, found)
    meta = {"from": sender, "subject": subject[:300],
            "date": email_date, "contract": contract}
    return list(found.values()), meta


# --- Inbox scan --------------------------------------------------------------

# A scan of 1000 emails takes minutes, and IMAP gives no feedback while it
# runs: without this the button just sits there and the app looks hung. The
# scan endpoint is a sync `def`, so FastAPI runs it in a threadpool and can
# still answer GET /email-import/progress from the event loop while it works.
# One scan at a time (single-user local app), so a plain dict is enough: each
# field is written by the worker thread and read by the poller, and CPython
# makes those individual assignments atomic.
_progress: dict = {
    "active": False, "phase": "idle", "emails_done": 0, "emails_total": 0,
    "staged": 0,
}

# One scan at a time, enforced — not just assumed. The dashboard can be open
# on the phone and the desktop at once (see serve.bat), and two overlapping
# scans would interleave their writes to `_progress` and race each other on
# the "already staged?" lookup: `imported_listings` has no unique constraint
# on (portal, portal_id), so the loser of that race stages a duplicate the
# review panel then shows twice. Same pattern as the scanner's `_scan_lock`.
_scan_run_lock = threading.Lock()


def get_progress() -> dict:
    """Snapshot of the running scan, for the UI to poll."""
    return dict(_progress)


def _purge_blank_pending(db: Session) -> int:
    """Removes pending rows that carry nothing to judge by.

    They were staged by earlier scans, before blank links were recognised as
    the boilerplate they are. Only `pending` rows: a `discarded` row is the
    user's decision and must survive forever — it is the memory that keeps a
    re-scan idempotent. Deleting a blank is safe because extraction no longer
    stages one, so it cannot come back.
    """
    blanks = db.scalars(select(ImportedListing).where(
        ImportedListing.status == "pending",
        ImportedListing.price.is_(None),
        ImportedListing.sqm.is_(None),
        ImportedListing.rooms.is_(None),
    )).all()
    removed = 0
    for row in blanks:
        if _clean_title(row.title or ""):
            continue  # a name is enough to review it
        db.delete(row)
        removed += 1
    return removed


def _store_entry(db: Session, entry: dict, meta: dict, summary: dict) -> None:
    portal, portal_id = entry["portal"], entry["portal_id"]
    if not _has_details(entry):
        summary["blank_links"] += 1
        return
    existing_listing = db.scalar(select(Listing).where(
        Listing.portal == portal, Listing.portal_id == portal_id
    ))
    if existing_listing:
        summary["already_tracked"] += 1
        if not existing_listing.image_url and entry.get("image_url"):
            existing_listing.image_url = entry["image_url"]
            from ..models import Property as _Property
            prop = db.get(_Property, existing_listing.property_id)
            if prop and not prop.image_url:
                prop.image_url = entry["image_url"]
        return
    staged = db.scalar(select(ImportedListing).where(
        ImportedListing.portal == portal,
        ImportedListing.portal_id == portal_id,
    ))
    if staged:
        # keep the row (whatever its status: a discarded ad must not come
        # back), but fill fields a richer email may provide
        summary["already_imported"] += 1
        if not staged.title and entry["title"]:
            staged.title = entry["title"]
        if not getattr(staged, "image_url", None) and entry.get("image_url"):
            staged.image_url = entry["image_url"]
            if getattr(staged, "property_id", None):
                from ..models import Property as _Property
                prop = db.get(_Property, staged.property_id)
                if prop and not prop.image_url:
                    prop.image_url = entry["image_url"]
                for l in (prop.listings if prop else []):
                    if not l.image_url:
                        l.image_url = entry["image_url"]
        for f in ("price", "sqm", "rooms"):
            if getattr(staged, f) is None and entry[f] is not None:
                setattr(staged, f, entry[f])
        return
    db.add(ImportedListing(
        portal=portal,
        portal_id=portal_id,
        url=CANONICAL_URL[portal].format(id=portal_id),
        title=entry["title"],
        price=entry["price"],
        rooms=entry["rooms"],
        sqm=entry["sqm"],
        image_url=entry.get("image_url", ""),
        contract=meta["contract"],
        email_from=meta["from"],
        email_subject=meta["subject"],
        email_date=meta["date"],
    ))
    db.flush()
    summary["imported"] += 1


def scan_inbox(
    db: Session,
    mode: str = "portals",
    senders: str = "",
    since_days: int = 365,
    max_emails: int = 200,
    client=None,
) -> dict:
    """Scans the INBOX (newest first, capped at `max_emails`) and stages every
    listing not already known. Returns a summary of what happened — the
    numbers are the user's only feedback, so each outcome is counted.

    `client` is injectable for tests: anything with select/search/fetch/logout.
    """
    if not _scan_run_lock.acquire(blocking=False):
        raise ImapError("An inbox scan is already running: wait for it to finish")
    summary = {
        "emails_scanned": 0, "emails_with_listings": 0, "listings_found": 0,
        "imported": 0, "already_tracked": 0, "already_imported": 0,
        "blank_links": 0, "blank_removed": 0,
    }
    _progress.update(active=True, phase="connecting", emails_done=0,
                     emails_total=0, staged=0)
    owns_client = client is None
    try:
        # inside the try: a refused login must still clear the progress flag,
        # or the UI would poll a scan that never started until a page reload
        if owns_client:
            client = _connect(load_settings())
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise ImapError("Could not open INBOX")
        _progress.update(phase="searching")
        try:
            status, data = client.search(
                None, _search_criteria(mode, senders, since_days)
            )
        except imaplib.IMAP4.error as e:
            raise ImapError(f"IMAP search failed: {e}") from e
        if status != "OK":
            raise ImapError("IMAP search failed")
        ids = data[0].split()
        selected = list(reversed(ids[-max_emails:]))  # newest first
        _progress.update(phase="fetching", emails_total=len(selected))
        for msg_id in selected:
            status, msg_data = client.fetch(msg_id, "(BODY.PEEK[])")
            _progress["emails_done"] += 1
            first = msg_data[0] if msg_data else None
            if status != "OK" or not first:
                continue
            raw = first[1] if isinstance(first, tuple) else first
            if not isinstance(raw, bytes):
                continue
            summary["emails_scanned"] += 1
            try:
                entries, meta = extract_listings(raw)
            except Exception:
                logger.exception("email-import: failed to parse a message")
                continue
            if not entries:
                continue
            summary["emails_with_listings"] += 1
            for entry in entries:
                summary["listings_found"] += 1
                _store_entry(db, entry, meta, summary)
            _progress["staged"] = summary["imported"]
        summary["blank_removed"] = _purge_blank_pending(db)
        db.commit()
    finally:
        # the poller must never be left believing a dead scan is still running
        _progress.update(active=False, phase="idle")
        if owns_client and client is not None:
            _logout(client)
        _scan_run_lock.release()
    logger.info("email-import: %s", summary)
    return summary


# --- Scheduled auto re-scan --------------------------------------------------

# The automatic re-scan runs unattended, so its parameters are fixed rather than
# taken from the manual UI. "portals" keeps it to genuine Immobiliare/Idealista
# alert mails (no address list to maintain); a rolling window wider than any
# plausible interval means an occasional stretch with the PC off is still caught
# on the next run (re-scans are idempotent — nothing is staged twice).
AUTO_SCAN_MODE = "portals"
AUTO_SCAN_SINCE_DAYS = 14
AUTO_SCAN_MAX_EMAILS = 300


def auto_scan_job() -> None:
    """Opt-in scheduled inbox re-scan (registered by the scheduler).

    Silent by design: staged listings wait in the review queue for an explicit
    accept (invariant 12), so a re-scan never notifies — it would be alerting
    about ads the user has not yet chosen to track. Fail-open like the rest of
    the background work: a mailbox that is unreachable, unconfigured, or busy
    with a manual scan is logged and skipped, never raised, so it cannot take
    the scheduler thread down.
    """
    settings = load_settings()
    if not settings.get("email_import_auto_scan"):
        return
    if not (settings.get("imap_host") and settings.get("imap_user")
            and settings.get("imap_password")):
        logger.info(
            "email-import auto-scan enabled but IMAP is not configured; skipping"
        )
        return
    db = SessionLocal()
    try:
        summary = scan_inbox(
            db, mode=AUTO_SCAN_MODE, since_days=AUTO_SCAN_SINCE_DAYS,
            max_emails=AUTO_SCAN_MAX_EMAILS,
        )
        logger.info("email-import auto-scan: %s", summary)
    except ImapError as e:
        # includes "a scan is already running": the manual scan wins, this run
        # is simply skipped and the next interval tries again
        logger.warning("email-import auto-scan skipped: %s", e)
    except Exception:
        logger.exception("email-import auto-scan failed")
    finally:
        db.close()


# --- Availability check ------------------------------------------------------

# Same shape as `_progress`, same reason: the check spends `request_delay_seconds`
# between listings, so a batch of fifty runs for minutes.
_check_progress: dict = {"active": False, "done": 0, "total": 0, "gone": 0}

# Serialized for a harsher reason than the scan: two concurrent batches double
# the request rate to the portals, and the pacing, the block-streak abort and
# the once-per-host warm-up all assume a single probe is talking to them.
_check_run_lock = threading.Lock()

# The scan must stay free of network calls to the portals (a thousand emails
# would mean a thousand ad pages); the check is the opposite: few listings, on
# demand, spaced out. Hence the cap — it is what keeps the two apart.
MAX_CHECKS_PER_CALL = 50

# Idealista's own scraper raises its floor to 8s because "DataDome is sensitive
# to request frequency" there; an ad page is not gentler than a search page.
MIN_PROBE_DELAY = {"immobiliare": 6.0, "idealista": 8.0}

# Once the portal has started refusing, every further request digs the hole
# deeper — and the block lands on the IP the real scans need. Five in a row is
# an answer: stop, and tell the user why the batch ended early.
BLOCK_STREAK_ABORT = 3

# When checking large batches (e.g. 218 listings), allow up to 2 cookie refreshes
# or deep session resets before aborting.
MAX_COOKIE_REFRESHES_PER_CHECK = 2


def get_check_progress() -> dict:
    """Snapshot of the running availability check, for the UI to poll."""
    return dict(_check_progress)


def _try_cookie_recovery(probe, portal: str, settings: dict, summary: dict) -> bool:
    """Recover from a block during the availability check by minting a fresh
    DataDome cookie in a headless browser and rebuilding the probe's session
    around it, so the batch can carry on instead of giving up.

    Opt-in (`datadome_auto_refresh`) and best-effort: a missing browser, a
    CAPTCHA it cannot pass headless, or a refresh failure all return False and
    the caller aborts as before. This is the *same* mechanism the scanner runs
    before a scan (invariant 18) — here it fires reactively, on a block, which
    is exactly when the cookie has demonstrably burned.
    """
    if not settings.get("datadome_auto_refresh"):
        return False
    from . import cookie_harvester
    if not cookie_harvester.is_available():
        return False
    logger.info("email-import: portal blocking; grabbing a fresh DataDome cookie")
    try:
        result = cookie_harvester.refresh_into_settings(portal, headless=True)
    except Exception:
        logger.exception("email-import: cookie recovery failed")
        return False
    if not result.get("ok"):
        return False
    # Rebuild the probe around the new cookie, back to the preferred handshake,
    # and force a re-warm of the homepage so the fresh cookie is carried in.
    probe._imp_index = 0
    probe.session = probe._new_session()
    probe._warmed_hosts = set()
    probe.was_blocked = False
    summary["cookie_refreshed"] = summary.get("cookie_refreshed", 0) + 1
    return True


def check_availability(db: Session, items: list[ImportedListing], skip_recent_hours: float = 6.0) -> dict:
    """Asks each portal whether these ads still exist, one at a time.

    This is the only place the import touches the portals, and only because
    the user pressed a button: the alternative — probing every staged listing
    during a scan — is hundreds of requests in a burst, which is how a
    residential IP earns a DataDome block (see the module docstring).

    An unreachable or blocked portal leaves `is_available` untouched: the
    listing keeps whatever was last known about it, and stays reviewable. And
    if the portal keeps refusing, the batch gives up rather than insisting: the
    IP it would get blocked on is the same one the scheduled scans depend on.
    """
    if not _check_run_lock.acquire(blocking=False):
        raise ImapError(
            "An availability check is already running: wait for it to finish"
        )
    try:
        return _check_availability_inner(db, items, skip_recent_hours)
    finally:
        _check_run_lock.release()


def _check_availability_inner(db: Session, items: list[ImportedListing], skip_recent_hours: float = 6.0) -> dict:
    settings = load_settings()
    configured = float(settings.get("request_delay_seconds") or 6.0)
    # the slowest portal in the batch sets the pace for all of it
    delay = max([configured] + [
        MIN_PROBE_DELAY.get(item.portal, 0.0) for item in items
    ])
    probe = AdProbe(delay_seconds=delay)
    summary = {"checked": 0, "gone": 0, "online": 0, "unknown": 0,
               "aborted": False, "capped": False, "last_error": None,
               "cookie_refreshed": 0}
    _check_progress.update(active=True, done=0, total=len(items), gone=0,
                           online=0, unknown=0, last_error=None)
    try:
        # Browser-first: open one persistent headless browser up front and run
        # the whole batch through it, so curl_cffi never earns a 403 on the
        # residential IP. Opt-in and best-effort — if Playwright is missing or
        # the flag is off, start_browser_session returns False and the batch
        # proceeds on curl_cffi exactly as before (invariant 16 unchanged).
        if settings.get("availability_browser_first") and hasattr(
                probe, "start_browser_session"):
            if probe.start_browser_session():
                probe._browser_primary = True
                logger.info("email-import: availability check running "
                            "browser-first (curl_cffi bypassed)")
            else:
                logger.info("email-import: browser-first requested but the "
                            "browser is unavailable; using curl_cffi")
        block_streak = 0
        refreshes_used = 0
        probes_used = 0
        for index, item in enumerate(items):
            if probes_used >= MAX_CHECKS_PER_CALL:
                # The cap bounds portal fetches, not selection size: rows
                # resolved from the dashboard or recently checked skip for
                # free, so re-running the batch resumes past them instead of
                # re-spending the budget on the same first fifty ids.
                summary["capped"] = True
                logger.info("email-import: probe budget (%d) spent, stopping "
                            "after %d listings", MAX_CHECKS_PER_CALL, index)
                break
            # If the dashboard already tracks this listing, resolve it from
            # the database — but only in the safe direction: a property still
            # seen by scans is certainly online. A "gone" status is NOT proof
            # the ad is offline: it only means no scan has seen it for a week,
            # which also happens when a profile was deleted or narrowed, or
            # the scans were blocked. Only a clear answer from the portal may
            # become False (invariant 16): a false "gone" invites a discard,
            # and discards are remembered forever. Gone and orphan listings
            # fall through to the HTTP probe.
            db_listing = db.execute(
                select(Listing).where(
                    Listing.portal == item.portal,
                    Listing.portal_id == item.portal_id
                )
            ).scalar_one_or_none()
            prop = db_listing.property if db_listing else None
            if prop is not None and prop.status in ("active", "filtered",
                                                    "hidden"):
                item.is_available = True
                item.last_checked_at = datetime.now(timezone.utc)
                summary["online"] += 1
                summary["checked"] += 1
                db.commit()
                _check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            from .availability_check import _is_recently_checked
            if (skip_recent_hours > 0 and len(items) > 1 and item.is_available is not None
                    and _is_recently_checked(item.last_checked_at, skip_recent_hours)):
                summary["gone" if item.is_available is False else "online"] += 1
                summary["checked"] += 1
                _check_progress.update(done=index + 1, gone=summary["gone"])
                continue

            probes_used += 1
            available = probe.check(item.url)
            item.last_checked_at = datetime.now(timezone.utc)
            if available is None:
                summary["unknown"] += 1
                if getattr(probe, "last_error", None):
                    summary["last_error"] = probe.last_error
            else:
                item.is_available = available
                summary["gone" if available is False else "online"] += 1
                if available is True and getattr(probe, "last_soup", None):
                    # Enrich missing image_url or title from live ad page
                    soup = probe.last_soup
                    if not getattr(item, "image_url", ""):
                        og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                        if og_img and og_img.get("content"):
                            item.image_url = str(og_img["content"]).strip()[:500]
                    if not item.title:
                        og_title = soup.find("meta", property="og:title")
                        if og_title and og_title.get("content"):
                            item.title = _clean_title(str(og_title["content"]))
            summary["checked"] += 1
            # each answer cost seconds of polite pacing: commit it now, so a
            # crash halfway through the batch does not throw the rest away
            db.commit()
            _check_progress.update(done=index + 1, gone=summary["gone"],
                                   online=summary["online"],
                                   unknown=summary["unknown"],
                                   last_error=summary["last_error"])

            block_streak = block_streak + 1 if probe.was_blocked else 0
            if block_streak >= BLOCK_STREAK_ABORT:
                if (refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK
                        and _try_cookie_recovery(
                            probe, item.portal, settings, summary)):
                    refreshes_used += 1
                    block_streak = 0
                    continue
                if refreshes_used < MAX_COOKIE_REFRESHES_PER_CHECK + 2 and len(getattr(probe, "impersonations", [])) > 1:
                    logger.info("email-import: portal rate limit / block streak reached, sleeping 12s and rotating session")
                    time.sleep(12.0)
                    probe._imp_index = (probe._imp_index + 1) % len(probe.impersonations)
                    if hasattr(probe, "_new_session"):
                        probe.session = probe._new_session()
                    probe._warmed_hosts = set()
                    probe.was_blocked = False
                    refreshes_used += 1
                    block_streak = 0
                    continue
                if (hasattr(probe, "start_browser_session")
                        and not getattr(probe, "_browser_primary", False)
                        and probe.start_browser_session()):
                    # Last resort, opt-in (invariant 18): switch the *rest of
                    # the batch* to the persistent browser instead of hammering
                    # a TLS session the portal already refused. Sticky, not
                    # per-ad: leaving curl_cffi as primary would re-earn a 403
                    # on every remaining listing before falling back here.
                    probe._browser_primary = True
                    logger.info("email-import: curl_cffi blocked repeatedly, switching the rest of the batch to the persistent browser session")
                    time.sleep(6.0)
                    block_streak = 0
                    continue
                logger.warning(
                    "email-import: portal blocking the availability check, "
                    "stopping after %s listings", summary["checked"],
                )
                summary["aborted"] = True
                break
            if index + 1 < len(items):
                probe.polite_sleep()
    finally:
        # hasattr: tests swap in fake probes without the browser machinery
        if hasattr(probe, "close_browser_session"):
            probe.close_browser_session()
        _check_progress.update(active=False)
    logger.info("email-import: availability check %s", summary)
    return summary


# --- Review actions ----------------------------------------------------------

def accept_import(db: Session, item: ImportedListing) -> Property:
    """Turns a staged listing into a real Property/Listing via the standard
    deduplication path: if the same ad (or the same physical house) is already
    tracked, it merges instead of duplicating. No notification is sent —
    notifications belong to the scanner, and these are historical finds."""
    raw = RawListing(
        portal=item.portal,
        portal_id=item.portal_id,
        url=item.url,
        contract=item.contract,
        title=item.title,
        price=item.price,
        sqm=item.sqm,
        rooms=item.rooms,
        city=item.city,
        zone=item.zone,
        image_url=getattr(item, "image_url", "") or "",
    )
    prop, _is_new, _price_changed = upsert_listing(db, raw)
    item.status = "accepted"
    item.property_id = prop.id
    db.commit()
    return prop


def profile_criteria(profile: SearchProfile, global_keywords: list[str]) -> dict:
    """Derives review-filter criteria from an existing search profile: the
    contract and city its URL encodes, plus its keywords added to the global
    ones — so "show me the imports matching the search I already monitor"
    is one click instead of retyping everything."""
    from urllib.parse import urlparse

    from ..scrapers.idealista import IdealistaScraper

    contract = detect_contract(profile.search_url)
    if profile.portal == "idealista":
        city = IdealistaScraper._city_from_url(profile.search_url)
    else:
        segments = [s for s in urlparse(profile.search_url).path.split("/") if s]
        # /vendita-case/milano/... — polygon URLs (search-list) have no city
        city = ""
        if len(segments) > 1 and segments[0] != "search-list":
            city = segments[1].replace("-", " ").title()
    keywords = [*global_keywords, *parse_keywords_csv(profile.excluded_keywords)]
    return {"contract": contract, "city": city, "keywords": keywords}
