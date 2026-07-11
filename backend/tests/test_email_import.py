"""Tests for the email inbox import (services/email_import.py).

Everything runs offline: a fake IMAP client serves handcrafted alert emails,
mirroring the real structure of portal notifications (HTML cards, every link
wrapped in a click-tracking redirect that percent-encodes the target URL).
"""
from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ImportedListing, Listing, SearchProfile
from app.services.deduplicator import upsert_listing
from app.services import email_import
from app.services.email_import import (
    ImapError, _search_criteria, accept_import, check_availability,
    extract_listings, get_check_progress, get_progress, profile_criteria,
    scan_inbox,
)
from app.scrapers.base import RawListing


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _email(html: str, subject="3 nuovi annunci per la tua ricerca",
           sender="noreply@immobiliare.it", plain="see html") -> bytes:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Immobiliare.it <{sender}>"
    msg["Date"] = "Mon, 01 Jun 2026 10:00:00 +0200"
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


# Two cards, like a real digest: links wrapped in tracking redirects (target
# percent-encoded) plus a plain link, price/size/rooms as sibling text.
TWO_CARDS_HTML = """
<html><body><table>
  <tr><td>
    <a href="https://click.mail.immobiliare.it/track?url=https%3A%2F%2Fwww.immobiliare.it%2Fannunci%2F12345%2F">
      <img src="x.jpg" alt="Trilocale via Roma"/>
    </a>
    <a href="https://www.immobiliare.it/annunci/12345/">Trilocale via Roma, Milano</a>
    <p>&euro; 250.000 &middot; 90 m&#178; &middot; 3 locali</p>
  </td></tr>
  <tr><td>
    <a href="https://www.immobiliare.it/annunci/67890/">Bilocale corso Buenos Aires</a>
    <p>&euro; 180.000 &middot; 55 m&#178; &middot; 2 locali</p>
  </td></tr>
</table></body></html>
"""


class FakeImap:
    """The minimum surface scan_inbox touches: select/search/fetch/logout."""

    def __init__(self, messages: list[bytes]):
        self.messages = messages
        self.criteria = ""
        self.readonly = None

    def select(self, mailbox, readonly=False) -> tuple[str, list[bytes]]:
        self.readonly = readonly
        return "OK", [str(len(self.messages)).encode()]

    def search(self, charset, criteria):
        self.criteria = criteria
        ids = b" ".join(str(i + 1).encode() for i in range(len(self.messages)))
        return "OK", [ids]

    def fetch(self, msg_id, spec):
        assert "PEEK" in spec  # read-only guarantee: never sets \Seen
        return "OK", [(b"1 (BODY[] {0})", self.messages[int(msg_id) - 1])]

    def logout(self):
        return "BYE", []


# --- Extraction ---------------------------------------------------------------


def test_extracts_cards_with_price_sqm_rooms():
    entries, meta = extract_listings(_email(TWO_CARDS_HTML))
    assert {e["portal_id"] for e in entries} == {"12345", "67890"}
    tri = next(e for e in entries if e["portal_id"] == "12345")
    assert tri["title"].startswith("Trilocale")
    assert tri["price"] == 250_000.0
    assert tri["sqm"] == 90.0
    assert tri["rooms"] == 3
    assert meta["from"] == "noreply@immobiliare.it"
    assert meta["contract"] == "sale"


def test_tracking_only_links_are_still_recognised():
    """Many alert templates wrap EVERY link in the tracker: the target URL
    only exists percent-encoded inside the redirect query string."""
    html = """<a href="https://click.x.it/y?u=https%3A%2F%2Fwww.idealista.it%2Fimmobile%2F555%2F">
              Bilocale zona Isola</a> <span>950 &euro; al mese</span>"""
    entries, meta = extract_listings(_email(html, subject="Nuove case in affitto"))
    assert entries[0]["portal"] == "idealista"
    assert entries[0]["portal_id"] == "555"
    assert meta["contract"] == "rent"          # subject says "affitto"
    assert entries[0]["price"] == 950.0        # rent bounds, not sale bounds


def test_plain_text_fallback():
    msg = EmailMessage()
    msg["Subject"] = "Nuovo annuncio"
    msg["From"] = "alerts@idealista.com"
    msg.set_content(
        "Bilocale 60 mq a 200.000 €\nhttps://www.idealista.it/immobile/777/"
    )
    entries, _ = extract_listings(msg.as_bytes())
    assert entries[0]["portal_id"] == "777"
    assert entries[0]["sqm"] == 60.0


def test_same_ad_linked_many_times_yields_one_entry():
    entries, _ = extract_listings(_email(TWO_CARDS_HTML))
    assert len(entries) == 2  # image link + title link of card 1 are merged


# --- Inbox scan and idempotency ------------------------------------------------


def test_scan_stages_pending_rows(db):
    client = FakeImap([_email(TWO_CARDS_HTML)])
    summary = scan_inbox(db, client=client)
    assert client.readonly is True
    assert summary["imported"] == 2
    rows = list(db.scalars(select(ImportedListing)))
    assert all(r.status == "pending" for r in rows)
    assert all(r.url.startswith("https://www.immobiliare.it/annunci/") for r in rows)


def test_rescan_is_idempotent_even_after_discard(db):
    """Re-scanning the same inbox must not resurrect anything: a discarded
    listing stays discarded — that row IS the memory of the rejection."""
    scan_inbox(db, client=FakeImap([_email(TWO_CARDS_HTML)]))
    for row in db.scalars(select(ImportedListing)):
        row.status = "discarded"
    db.commit()

    summary = scan_inbox(db, client=FakeImap([_email(TWO_CARDS_HTML)]))
    assert summary["imported"] == 0
    assert summary["already_imported"] == 2
    assert all(
        r.status == "discarded" for r in db.scalars(select(ImportedListing))
    )


def test_already_tracked_listings_are_not_staged(db):
    """An ad the scanner already follows must not show up for review."""
    upsert_listing(db, RawListing(
        portal="immobiliare", portal_id="12345",
        url="https://www.immobiliare.it/annunci/12345/",
        title="Trilocale", city="Milano", rooms=3, sqm=90.0, price=250_000.0,
        latitude=45.46, longitude=9.19,
    ))
    db.commit()
    summary = scan_inbox(db, client=FakeImap([_email(TWO_CARDS_HTML)]))
    assert summary["already_tracked"] == 1
    assert summary["imported"] == 1  # only the other card


def test_max_emails_caps_processing_from_the_newest(db):
    mails = [_email(TWO_CARDS_HTML), _email(
        '<a href="https://www.immobiliare.it/annunci/99/">Casa</a> € 100.000'
    )]
    summary = scan_inbox(db, client=FakeImap(mails), max_emails=1)
    # only the newest (last sequence number) message is read
    assert summary["emails_scanned"] == 1
    assert {r.portal_id for r in db.scalars(select(ImportedListing))} == {"99"}


# --- Junk links ------------------------------------------------------------------

# Real alert emails end with "if the link does not work, copy this address",
# whose anchor text *is* the URL. It used to be staged as a listing named
# "https://www.immobiliare.it/annunci/128621066/", priced "N/A" — unreviewable,
# and usually pointing at an ad that had already been taken down.
BARE_LINK_HTML = """
<html><body>
  <p>Se il link non funziona, copia questo indirizzo:
    <a href="https://www.immobiliare.it/annunci/128621066/">https://www.immobiliare.it/annunci/128621066/</a>
  </p>
</body></html>
"""


def test_bare_link_with_no_details_is_not_staged(db):
    summary = scan_inbox(db, client=FakeImap([_email(BARE_LINK_HTML)]))
    assert summary["listings_found"] == 1   # the link was seen…
    assert summary["blank_links"] == 1      # …and recognised as boilerplate
    assert summary["imported"] == 0
    assert list(db.scalars(select(ImportedListing))) == []


def test_a_url_is_never_used_as_the_title(db):
    """The link text may be the URL itself while the card still has a price:
    keep the listing, drop the pseudo-title (the UI falls back to the subject)."""
    html = """<p><a href="https://www.immobiliare.it/annunci/222/">
              https://www.immobiliare.it/annunci/222/</a> &euro; 300.000 &middot; 70 m&#178;</p>"""
    entries, _ = extract_listings(_email(html))
    assert entries[0]["title"] == ""
    assert entries[0]["price"] == 300_000.0

    scan_inbox(db, client=FakeImap([_email(html)]))
    assert db.scalar(select(ImportedListing)).portal_id == "222"


def test_call_to_action_text_is_not_a_title():
    """"Vedi l'annuncio ›" is a button, not the name of a house. The card's
    real title wins anyway (longest one), but a CTA-only card must not keep it."""
    html = """<p><a href="https://www.idealista.it/immobile/333/">Vedi l&rsquo;annuncio &rsaquo;</a>
              <span>950 &euro; al mese</span></p>"""
    entries, _ = extract_listings(_email(html, subject="Affitto"))
    assert entries[0]["title"] == ""
    assert entries[0]["price"] == 950.0


def test_template_placeholder_ids_are_ignored():
    """Some templates ship an unfilled "/annunci/0/" link in a hidden block."""
    html = '<a href="https://www.immobiliare.it/annunci/0/">Casa</a> &euro; 100.000'
    entries, _ = extract_listings(_email(html))
    assert entries == []


def test_blank_pending_rows_are_cleaned_up_but_discards_survive(db):
    """Rows staged before blank links were filtered out are removed on the next
    scan. Discarded rows are never touched: they are the memory of a rejection
    (invariant 12), and deleting one would resurrect the listing."""
    db.add(ImportedListing(
        portal="immobiliare", portal_id="900",
        url="https://www.immobiliare.it/annunci/900/",
        title="https://www.immobiliare.it/annunci/900/", contract="sale",
        status="pending",
    ))
    db.add(ImportedListing(   # blank, but the user already ruled on it
        portal="immobiliare", portal_id="901",
        url="https://www.immobiliare.it/annunci/901/",
        title="", contract="sale", status="discarded",
    ))
    db.add(ImportedListing(   # pending and priceless, but it has a name
        portal="immobiliare", portal_id="902",
        url="https://www.immobiliare.it/annunci/902/",
        title="Trilocale via Roma", contract="sale", status="pending",
    ))
    db.commit()

    summary = scan_inbox(db, client=FakeImap([]))
    assert summary["blank_removed"] == 1
    assert {r.portal_id for r in db.scalars(select(ImportedListing))} == {"901", "902"}


# --- Review actions -------------------------------------------------------------


def test_accept_creates_property_through_dedup(db):
    scan_inbox(db, client=FakeImap([_email(TWO_CARDS_HTML)]))
    item = db.scalar(select(ImportedListing).where(
        ImportedListing.portal_id == "12345"
    ))
    prop = accept_import(db, item)
    assert item.status == "accepted"
    assert item.property_id == prop.id
    assert prop.current_min_price == 250_000.0
    listing = db.scalar(select(Listing).where(Listing.portal_id == "12345"))
    assert listing.property_id == prop.id


# --- Availability check ----------------------------------------------------------


def _staged(db, portal_id: str) -> ImportedListing:
    row = ImportedListing(
        portal="immobiliare", portal_id=portal_id,
        url=f"https://www.immobiliare.it/annunci/{portal_id}/",
        title=f"Trilocale {portal_id}", price=250_000.0, contract="sale",
    )
    db.add(row)
    db.commit()
    return row


def _fake_probe(db, monkeypatch, answers: dict[str, bool | None]):
    """Replaces the network probe, and its 6-second politeness sleep."""
    class FakeProbe:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False

        def check(self, url):
            return answers[url]

        def polite_sleep(self):
            raise AssertionError("the test must not sleep")

    monkeypatch.setattr(email_import, "AdProbe", FakeProbe)


def test_check_marks_gone_listings_and_leaves_the_live_ones(db, monkeypatch):
    alive, dead = _staged(db, "111"), _staged(db, "222")
    _fake_probe(db, monkeypatch, {alive.url: True, dead.url: False})

    summary = check_availability(db, [alive])   # one at a time: no polite_sleep
    assert summary == {"checked": 1, "gone": 0, "online": 1, "unknown": 0,
                       "aborted": False, "last_error": None}
    assert alive.is_available is True and alive.last_checked_at is not None

    summary = check_availability(db, [dead])
    assert summary["gone"] == 1
    assert dead.is_available is False
    # flagged, never auto-discarded: the user still decides
    assert dead.status == "pending"


def test_an_unknown_answer_never_overwrites_what_was_known(db, monkeypatch):
    """A DataDome block answers None. Writing that into `is_available` would
    erase a previous "online", and a listing shown as unavailable is one the
    user discards — irreversibly."""
    item = _staged(db, "333")
    item.is_available = True
    db.commit()

    _fake_probe(db, monkeypatch, {item.url: None})
    summary = check_availability(db, [item])

    assert summary["unknown"] == 1
    assert item.is_available is True          # untouched
    assert item.last_checked_at is not None   # but we did try


def test_the_check_gives_up_once_the_portal_starts_refusing(db, monkeypatch):
    """Insisting against a portal that already said no deepens the block — and
    it lands on the IP the scheduled scans need. Three refusals in a row end
    the batch, leaving the untouched listings untouched."""
    items = [_staged(db, str(500 + n)) for n in range(6)]

    class BlockingProbe:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False
            self.calls = 0

        def check(self, url):
            self.calls += 1
            self.was_blocked = True   # DataDome refuses everything, from now on
            return None

        def polite_sleep(self):
            pass

    monkeypatch.setattr(email_import, "AdProbe", BlockingProbe)
    summary = check_availability(db, items)

    assert summary["aborted"] is True
    assert summary["checked"] == 3          # not 6: it stopped knocking
    assert all(i.is_available is None for i in items)


def test_a_slow_portal_sets_the_pace_for_the_whole_batch(db, monkeypatch):
    """Idealista's scraper floors its delay at 8s ("sensitive to request
    frequency"); an ad page is no gentler than a search page."""
    seen_delays = []

    class FakeProbe:
        def __init__(self, delay_seconds=6.0):
            seen_delays.append(delay_seconds)
            self.was_blocked = False

        def check(self, url):
            return True

        def polite_sleep(self):
            pass

    monkeypatch.setattr(email_import, "AdProbe", FakeProbe)
    immobiliare = _staged(db, "601")
    idealista = ImportedListing(
        portal="idealista", portal_id="602",
        url="https://www.idealista.it/immobile/602/", contract="sale",
    )
    db.add(idealista)
    db.commit()

    check_availability(db, [immobiliare])
    check_availability(db, [immobiliare, idealista])
    assert seen_delays == [6.0, 8.0]


def test_check_progress_clears_even_when_the_probe_explodes(db, monkeypatch):
    item = _staged(db, "444")

    class Exploding:
        def __init__(self, delay_seconds=6.0):
            pass

        def check(self, url):
            raise RuntimeError("boom")

    monkeypatch.setattr(email_import, "AdProbe", Exploding)
    with pytest.raises(RuntimeError):
        check_availability(db, [item])
    assert get_check_progress()["active"] is False


def test_answers_survive_a_crash_later_in_the_batch(db, monkeypatch):
    """Every answer costs seconds of polite pacing, so each one is committed
    as it arrives: a probe exploding on listing #2 must not throw away what
    listing #1 already established."""
    first, second = _staged(db, "445"), _staged(db, "446")

    class ExplodesOnSecond:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False

        def check(self, url):
            if url == first.url:
                return False
            raise RuntimeError("boom")

        def polite_sleep(self):
            pass

    monkeypatch.setattr(email_import, "AdProbe", ExplodesOnSecond)
    with pytest.raises(RuntimeError):
        check_availability(db, [first, second])
    db.rollback()  # discard any uncommitted leftovers, as FastAPI would
    assert first.is_available is False      # committed before the crash
    assert second.is_available is None


# --- Concurrency guards -----------------------------------------------------
#
# The dashboard can be open on the phone and the desktop at once (serve.bat),
# so "the user won't double-click" is not an argument. Two overlapping inbox
# scans race each other on the "already staged?" lookup — imported_listings
# has no unique constraint, so the loser stages a duplicate — and two
# overlapping availability checks double the request rate to the portals,
# defeating the pacing and the block-streak abort. Both operations therefore
# refuse to start while another run holds their module lock, like run_scan.


def test_a_second_inbox_scan_is_refused_while_one_runs(db):
    assert email_import._scan_run_lock.acquire(blocking=False)
    try:
        with pytest.raises(ImapError, match="already running"):
            scan_inbox(db, client=FakeImap([]))
    finally:
        email_import._scan_run_lock.release()
    # the refusal must not poison the lock: the next scan runs normally
    assert scan_inbox(db, client=FakeImap([]))["emails_scanned"] == 0


def test_a_second_availability_check_is_refused_while_one_runs(db, monkeypatch):
    item = _staged(db, "447")
    _fake_probe(db, monkeypatch, {item.url: True})
    assert email_import._check_run_lock.acquire(blocking=False)
    try:
        with pytest.raises(ImapError, match="already running"):
            check_availability(db, [item])
    finally:
        email_import._check_run_lock.release()
    assert check_availability(db, [item])["online"] == 1


# --- Search criteria and profile filter -----------------------------------------


def test_address_mode_requires_senders():
    with pytest.raises(ImapError):
        _search_criteria("address", "", 365)


def test_quotes_in_senders_cannot_break_the_search():
    """FROM terms are quoted strings: a stray quote pasted along with the
    address would escape them and abort the whole IMAP SEARCH."""
    criteria = _search_criteria("address", '"agenzia@example.it"', 365)
    assert 'FROM "agenzia@example.it"' in criteria
    # an input that is nothing but quotes sanitizes down to no sender at all
    with pytest.raises(ImapError):
        _search_criteria("address", '"" , \\', 365)


def test_criteria_use_english_month_names():
    """IMAP dates must be English regardless of the OS locale: an Italian
    Windows would produce "giu" with strftime and break the SEARCH."""
    criteria = _search_criteria("portals", "", 365)
    assert "SINCE" in criteria
    assert not any(m in criteria for m in ("gen", "mag", "giu", "lug", "ott", "dic"))


def test_profile_criteria_derives_contract_city_and_keywords():
    profile = SearchProfile(
        name="x", portal="immobiliare",
        search_url="https://www.immobiliare.it/affitto-case/milano/?prezzoMassimo=1200",
        excluded_keywords="asta, piano terra",
    )
    crit = profile_criteria(profile, ["seminterrato"])
    assert crit["contract"] == "rent"
    assert crit["city"] == "Milano"
    assert crit["keywords"] == ["seminterrato", "asta", "piano terra"]


def test_profile_criteria_idealista_zone_url():
    profile = SearchProfile(
        name="x", portal="idealista",
        search_url="https://www.idealista.it/vendita-case/sesto-san-giovanni-milano/",
        excluded_keywords="",
    )
    crit = profile_criteria(profile, [])
    assert crit["city"] == "Sesto San Giovanni"
    assert crit["contract"] == "sale"


# --- Scan progress -------------------------------------------------------------


def test_progress_advances_during_the_scan_and_clears_at_the_end(db):
    """Scanning a thousand messages takes minutes and IMAP reports nothing while
    it runs, so the UI polls this state. It is observed *mid-scan*: a snapshot
    taken only at the end would pass while the counter stayed at zero."""
    seen = []

    class ObservingImap(FakeImap):
        def fetch(self, msg_id, spec):
            seen.append(get_progress())
            return super().fetch(msg_id, spec)

    mails = [_email(TWO_CARDS_HTML) for _ in range(3)]
    scan_inbox(db, client=ObservingImap(mails))

    # the total is known before the first fetch (the IMAP search answered),
    # and the counter names the email about to be read, not the one after it
    assert [p["emails_done"] for p in seen] == [0, 1, 2]
    assert all(p["active"] and p["emails_total"] == 3 for p in seen)
    assert all(p["phase"] == "fetching" for p in seen)
    # the last observation still shows the listings staged so far
    assert seen[-1]["staged"] == 2

    after = get_progress()
    assert after["active"] is False and after["phase"] == "idle"


def test_progress_clears_when_the_scan_fails(db):
    """A crashed scan must not leave the UI polling forever: `active` is
    cleared in a finally, including when the mailbox refuses to open."""
    class BrokenImap(FakeImap):
        def select(self, mailbox, readonly=False):
            return "NO", [b"mailbox unavailable"]

    with pytest.raises(ImapError):
        scan_inbox(db, client=BrokenImap([_email(TWO_CARDS_HTML)]))

    assert get_progress()["active"] is False


def test_check_availability_uses_db_listing(db, monkeypatch):
    """A listing the dashboard already tracks is resolved offline — but only
    towards "online". A property just seen by a scan (active/filtered/hidden)
    is certainly live, so no request is spent on it. A "gone" status is NOT
    trusted as proof the ad is offline: it only means no scan has seen it for
    a week, which also happens when the profile was deleted or the scans were
    blocked. Trusting it once marked live ads as gone offline, inviting a
    discard that is remembered forever — so "gone" still goes through the
    HTTP probe (invariant 16: only the portal itself may say False)."""
    staged = _staged(db, "701")

    from app.models import Listing, Property
    import uuid
    prop = Property(
        fingerprint=str(uuid.uuid4()),
        status="active",
    )
    db.add(prop)
    db.commit()

    db_listing = Listing(
        property_id=prop.id,
        portal=staged.portal,
        portal_id=staged.portal_id,
        url=staged.url,
    )
    db.add(db_listing)
    db.commit()

    # any probe.check() call would be a network request the DB already answers
    class FailingProbe:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False
        def check(self, url):
            raise AssertionError("AdProbe should not be called")
        def polite_sleep(self):
            pass

    monkeypatch.setattr(email_import, "AdProbe", FailingProbe)

    summary = check_availability(db, [staged])
    assert summary["online"] == 1
    assert summary["gone"] == 0
    assert staged.is_available is True

    # a "gone" property must NOT resolve offline: the probe is consulted, and
    # here the portal says the ad is actually still up
    staged2 = ImportedListing(
        portal="immobiliare", portal_id="702",
        url="https://www.immobiliare.it/annunci/702/", contract="sale",
    )
    db.add(staged2)

    prop2 = Property(
        fingerprint=str(uuid.uuid4()),
        status="gone",
    )
    db.add(prop2)
    db.commit()

    db_listing2 = Listing(
        property_id=prop2.id,
        portal=staged2.portal,
        portal_id=staged2.portal_id,
        url=staged2.url,
    )
    db.add(db_listing2)
    db.commit()

    class StillOnlineProbe:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False
            self.calls = 0
        def check(self, url):
            self.calls += 1
            return True
        def polite_sleep(self):
            pass

    probes = []
    monkeypatch.setattr(
        email_import, "AdProbe",
        lambda delay_seconds=6.0: probes.append(StillOnlineProbe()) or probes[-1],
    )
    summary2 = check_availability(db, [staged2])
    assert probes[-1].calls == 1
    assert summary2["online"] == 1
    assert summary2["gone"] == 0
    assert staged2.is_available is True


def test_check_availability_handles_orphan_listing(db, monkeypatch):
    """If a Listing exists but has no associated Property (orphan listing),
    check_availability should not crash and should fall back to the HTTP probe."""
    staged = _staged(db, "801")

    # an orphan Listing pointing at a Property that does not exist
    from app.models import Listing
    db_listing = Listing(
        property_id=99999,  # no such Property
        portal=staged.portal,
        portal_id=staged.portal_id,
        url=staged.url,
    )
    db.add(db_listing)
    db.commit()

    # fake probe answering "still online", proving the HTTP fallback was used
    class FakeProbe:
        def __init__(self, delay_seconds=6.0):
            self.was_blocked = False
        def check(self, url):
            return True
        def polite_sleep(self):
            pass

    monkeypatch.setattr(email_import, "AdProbe", FakeProbe)

    summary = check_availability(db, [staged])
    assert summary["online"] == 1
    assert summary["checked"] == 1
    assert staged.is_available is True


# --- Scheduled auto re-scan ---------------------------------------------------

def _memory_sessionmaker():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_auto_scan_does_nothing_when_disabled(monkeypatch):
    """Opt-in: with the flag off, the job must not open any IMAP connection —
    the app never touches the mailbox on a schedule the user did not enable."""
    called = []
    monkeypatch.setattr(email_import, "scan_inbox",
                        lambda *a, **k: called.append(True))
    monkeypatch.setattr(email_import, "load_settings",
                        lambda: {"email_import_auto_scan": False})
    email_import.auto_scan_job()
    assert not called


def test_auto_scan_skips_when_imap_unconfigured(monkeypatch):
    """Enabled but no credentials: skip quietly rather than raising into the
    scheduler thread (there is nothing to connect to)."""
    called = []
    monkeypatch.setattr(email_import, "scan_inbox",
                        lambda *a, **k: called.append(True))
    monkeypatch.setattr(email_import, "load_settings",
                        lambda: {"email_import_auto_scan": True, "imap_host": ""})
    email_import.auto_scan_job()
    assert not called


def test_auto_scan_stages_silently(monkeypatch):
    """The happy path: it runs the real scan (portal-only, its own session and
    IMAP client) and stages listings as `pending`. Nothing is accepted and no
    notification is sent — the staged rows wait in the review queue, which is
    the whole point of keeping this silent (invariant 12)."""
    Session = _memory_sessionmaker()
    monkeypatch.setattr(email_import, "SessionLocal", Session)
    monkeypatch.setattr(email_import, "_connect",
                        lambda settings: FakeImap([_email(TWO_CARDS_HTML)]))
    monkeypatch.setattr(email_import, "load_settings", lambda: {
        "email_import_auto_scan": True,
        "imap_host": "imap.gmail.com", "imap_user": "u", "imap_password": "p",
    })

    email_import.auto_scan_job()

    rows = Session().scalars(select(ImportedListing)).all()
    assert {r.portal_id for r in rows} == {"12345", "67890"}
    assert all(r.status == "pending" for r in rows)


def test_auto_scan_is_fail_open(monkeypatch):
    """A scan blowing up (a broken mailbox, or a manual scan already holding the
    lock) must be swallowed: the scheduler thread has to survive to try again on
    the next interval."""
    class _Dummy:
        def close(self):
            pass

    monkeypatch.setattr(email_import, "SessionLocal", lambda: _Dummy())
    monkeypatch.setattr(email_import, "load_settings", lambda: {
        "email_import_auto_scan": True,
        "imap_host": "h", "imap_user": "u", "imap_password": "p",
    })

    def _imap_boom(*a, **k):
        raise ImapError("mailbox refused the connection")

    def _unexpected_boom(*a, **k):
        raise RuntimeError("something unforeseen")

    monkeypatch.setattr(email_import, "scan_inbox", _imap_boom)
    email_import.auto_scan_job()  # ImapError: must not propagate

    monkeypatch.setattr(email_import, "scan_inbox", _unexpected_boom)
    email_import.auto_scan_job()  # any Exception: must not propagate either

