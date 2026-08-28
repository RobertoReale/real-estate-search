"""The opt-in LLM reading of a listing's text. Offline throughout: the chat
call is mocked, exactly as `test_llm_parser.py` mocks it, so the whole
prompt/validate/store path runs with no network (invariant 17's rule).

Two properties are pinned harder than the rest, because they are what makes
this feature safe rather than merely useful: it must call nothing while it is
off (a scan or a card opening that quietly reached a model would be the exact
"work the user did not ask for" the opt-in exists to prevent), and whatever the
model answers must arrive bounded and inside the known vocabularies — a card
renders this text straight.
"""

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import save_settings
from app.database import Base
from app.models import Listing, Property, PropertyAudit
from app.services import data_reset, listing_auditor

FULL_REPLY = json.dumps(
    {
        "summary": "Third floor with a lift, sold with a sitting tenant.",
        "condition": "good",
        "tenant": "yes",
        "costs": ["Building fees 1,800 EUR/year (spese condominiali)"],
        "concerns": ["Tenant in place until 2028 (locato)"],
        "negotiation": ["On the market since January"],
    }
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


@pytest.fixture
def prop(db):
    p = Property(
        fingerprint="fp",
        title="Trilocale via Verdi",
        city="Torino",
        zone="Centro",
        sqm=95,
        rooms=3,
        floor="3",
        contract="sale",
        current_min_price=250000,
    )
    p.listings = [
        Listing(
            portal="immobiliare",
            portal_id="1",
            url="https://immobiliare.it/annunci/1",
            agency="Studio Rossi",
            description="Appartamento al terzo piano con ascensore, attualmente locato.",
        )
    ]
    db.add(p)
    db.commit()
    return p


def _enable(monkeypatch, reply, *, calls=None, model="qwen2.5"):
    """Turn the auditor on and answer the next chat call with `reply`."""
    save_settings(
        {
            "listing_audit_enabled": True,
            "llm_base_url": "http://localhost:11434/v1",
            "llm_model": model,
        }
    )

    def fake(base_url, api_key, model, system, user):
        if calls is not None:
            calls.append({"model": model, "system": system, "user": user})
        return reply

    monkeypatch.setattr(listing_auditor, "chat_completion", fake)


def _never_called(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the model must not be called here")

    monkeypatch.setattr(listing_auditor, "chat_completion", boom)


# --- the opt-in ------------------------------------------------------------


def test_it_is_off_by_default_and_calls_nothing(db, prop, monkeypatch):
    _never_called(monkeypatch)
    with pytest.raises(listing_auditor.ListingAuditError):
        listing_auditor.audit_property(db, prop)
    assert db.scalar(select(PropertyAudit)) is None


def test_enabled_but_unconfigured_says_so_instead_of_calling(db, prop, monkeypatch):
    # Ticking the box without filling in the endpoint is a half-configured
    # feature, not a reason to POST to nowhere and report a connection error.
    save_settings({"listing_audit_enabled": True})
    _never_called(monkeypatch)
    with pytest.raises(listing_auditor.ListingAuditError, match="No language model"):
        listing_auditor.audit_property(db, prop)


def test_is_configured_needs_all_three(monkeypatch):
    assert not listing_auditor.is_configured({"listing_audit_enabled": True})
    assert not listing_auditor.is_configured(
        {"listing_audit_enabled": False, "llm_base_url": "u", "llm_model": "m"}
    )
    assert listing_auditor.is_configured(
        {"listing_audit_enabled": True, "llm_base_url": "u", "llm_model": "m"}
    )


def test_an_ad_with_no_description_has_nothing_to_read(db, prop, monkeypatch):
    prop.listings[0].description = ""
    db.commit()
    _enable(monkeypatch, FULL_REPLY)
    with pytest.raises(listing_auditor.ListingAuditError, match="no description"):
        listing_auditor.audit_property(db, prop)


# --- what is sent, and what comes back -------------------------------------


def test_the_reply_becomes_the_shape_the_card_renders(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    audit = listing_auditor.audit_property(db, prop)
    assert audit["condition"] == "good"
    assert audit["tenant"] == "yes"
    assert audit["costs"] == ["Building fees 1,800 EUR/year (spese condominiali)"]
    assert audit["negotiation"] == ["On the market since January"]
    assert audit["model"] == "qwen2.5"
    assert audit["cached"] is False and audit["stale"] is False


def test_the_model_is_given_the_ad_text_and_the_facts_it_must_not_infer(db, prop, monkeypatch):
    calls: list[dict] = []
    _enable(monkeypatch, FULL_REPLY, calls=calls)
    listing_auditor.audit_property(db, prop)
    sent = calls[0]["user"]
    assert "attualmente locato" in sent  # the ad's own words
    assert "95 sqm" in sent and "3 rooms" in sent and "250000 EUR" in sent
    assert "Studio Rossi" in sent


def test_the_longest_description_wins_across_merged_ads(db, prop, monkeypatch):
    prop.listings.append(
        Listing(
            portal="idealista",
            portal_id="2",
            url="https://idealista.it/immobile/2",
            description="Trilocale luminoso in palazzo signorile, riscaldamento "
            "centralizzato, spese condominiali 150 euro al mese, terzo piano.",
        )
    )
    db.commit()
    calls: list[dict] = []
    _enable(monkeypatch, FULL_REPLY, calls=calls)
    listing_auditor.audit_property(db, prop)
    # Several agencies publish the same flat and one of them wrote more than
    # "trilocale luminoso": that is the copy worth reading.
    assert "spese condominiali 150 euro al mese" in calls[0]["user"]


def test_a_malformed_reply_stores_nothing_and_reports_it(db, prop, monkeypatch):
    _enable(monkeypatch, "I am a helpful assistant and this is not JSON")
    with pytest.raises(listing_auditor.ListingAuditError, match="did not answer"):
        listing_auditor.audit_property(db, prop)
    assert db.scalar(select(PropertyAudit)) is None


def test_an_unreachable_model_reports_instead_of_raising_its_own_error(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)

    def boom(*a, **k):
        raise ConnectionError("server down")

    monkeypatch.setattr(listing_auditor, "chat_completion", boom)
    with pytest.raises(listing_auditor.ListingAuditError, match="server down"):
        listing_auditor.audit_property(db, prop)


# --- bounding the answer ---------------------------------------------------


def test_unknown_vocabulary_degrades_to_unknown(db, prop, monkeypatch):
    _enable(monkeypatch, json.dumps({"condition": "immacolato", "tenant": "maybe"}))
    audit = listing_auditor.audit_property(db, prop)
    # A value no screen can render is worse than the admission that the text
    # did not say — and "maybe a tenant" is exactly the invention to refuse.
    assert audit["condition"] == "unknown"
    assert audit["tenant"] == "unknown"


def test_a_boolean_tenant_is_understood(db, prop, monkeypatch):
    # Models answer this one as a boolean about as often as as a string, and
    # dropping the `true` would read on the card as "no tenant mentioned".
    _enable(monkeypatch, json.dumps({"tenant": True}))
    assert listing_auditor.audit_property(db, prop)["tenant"] == "yes"


def test_an_essay_is_bounded_before_it_reaches_the_card(db, prop, monkeypatch):
    _enable(
        monkeypatch,
        json.dumps(
            {
                "summary": "x" * 900,
                "costs": ["c" * 500, *[f"item {i}" for i in range(20)], "", 42, None],
                "concerns": "not a list at all",
            }
        ),
    )
    audit = listing_auditor.audit_property(db, prop)
    assert len(audit["summary"]) == listing_auditor.MAX_SUMMARY_CHARS
    assert len(audit["costs"]) == listing_auditor.MAX_ITEMS
    assert all(len(c) <= listing_auditor.MAX_ITEM_CHARS for c in audit["costs"])
    assert audit["concerns"] == []  # a string is not a list of findings


# --- remembering the answer ------------------------------------------------


def test_the_second_press_is_free(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    _never_called(monkeypatch)
    again = listing_auditor.audit_property(db, prop)
    assert again["cached"] is True and again["condition"] == "good"


def test_force_re_asks_the_same_text(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    _enable(monkeypatch, json.dumps({"condition": "to_renovate"}))
    assert listing_auditor.audit_property(db, prop, force=True)["condition"] == "to_renovate"
    assert db.scalar(select(PropertyAudit).where(PropertyAudit.property_id == prop.id))


def test_a_rewritten_ad_is_read_again(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    prop.listings[0].description = "Ristrutturato nel 2024, libero subito."
    db.commit()
    # The stored answer is about text nobody can see any more: it is still
    # shown (same property), but flagged rather than presented as current.
    stored = listing_auditor.stored_audit(db, prop)
    assert stored is not None and stored["stale"] is True
    _enable(monkeypatch, json.dumps({"condition": "renovated", "tenant": "no"}))
    fresh = listing_auditor.audit_property(db, prop)
    assert fresh["condition"] == "renovated" and fresh["stale"] is False
    assert len(db.scalars(select(PropertyAudit)).all()) == 1  # updated, not duplicated


def test_switching_model_re_asks(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    # A different model is a different answer, so the row it wrote is not one.
    _enable(monkeypatch, json.dumps({"condition": "new"}), model="llama3.1")
    fresh = listing_auditor.audit_property(db, prop)
    assert fresh["model"] == "llama3.1" and fresh["condition"] == "new"


def test_stored_audit_never_calls_the_model(db, prop, monkeypatch):
    _never_called(monkeypatch)
    # Nothing asked for yet: the card opening must be free, so this reads the
    # row and answers "none" rather than producing one.
    assert listing_auditor.stored_audit(db, prop) is None


def test_an_unreadable_row_is_treated_as_absent(db, prop, monkeypatch):
    db.add(PropertyAudit(property_id=prop.id, text_digest="x", model="m", payload="{oops"))
    db.commit()
    _never_called(monkeypatch)
    assert listing_auditor.stored_audit(db, prop) is None


# --- the audit never outlives its property ---------------------------------


def test_deleting_a_property_takes_its_audit(db, prop, monkeypatch):
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    db.delete(prop)
    db.commit()
    assert db.scalar(select(PropertyAudit)) is None


def test_clearing_the_dashboard_takes_the_audits(db, prop, monkeypatch):
    # The Core deletes in data_reset skip the ORM cascade, so this table needs
    # naming there explicitly — same trap as property_tags.
    _enable(monkeypatch, FULL_REPLY)
    listing_auditor.audit_property(db, prop)
    data_reset.clear_dashboard(db)
    assert db.scalar(select(PropertyAudit)) is None
