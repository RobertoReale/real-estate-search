"""Tests for the "Repair data" maintenance action.

Regression coverage for a real dashboard bug: room-share listings scraped
under a generic "Appartamento in affitto" title survived "Repair data"
untouched, because `is_bad_title` only recognized the sale-side placeholder
strings ("appartamento in vendita" and friends) and not their rent mirror."""
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing
from app.services.repair_listings import is_bad_title, repair_empty_listings_locally


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(
        portal="immobiliare", portal_id="111",
        url="https://www.immobiliare.it/annunci/111/",
        contract="rent", title="Appartamento in affitto",
        city="Milano", zone="Città Studi - 2 persone",
        rooms=None, sqm=None, price=1100.0,
    )
    base.update(kwargs)
    return RawListing(**base)


def test_is_bad_title_recognizes_rent_placeholders_like_sale_ones():
    for placeholder in (
        "Appartamento in affitto", "In affitto a Milano, Milano",
        "Residenziale in affitto a Milano",
    ):
        assert is_bad_title(placeholder) is True
    # sale mirrors keep working
    assert is_bad_title("Appartamento in vendita") is True
    assert is_bad_title("Trilocale luminoso in Navigli") is False


def test_repair_replaces_generic_rent_title():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()

    prop = upsert_listing(db, _raw())[0]
    db.commit()
    assert prop.title == "Appartamento in affitto"

    summary = repair_empty_listings_locally(db)

    db.refresh(prop)
    assert summary["properties_fixed"] >= 1
    assert prop.title != "Appartamento in affitto"
    assert "Città Studi" in prop.title or "Milano" in prop.title
