"""Tests for the "Repair data" maintenance action.

Regression coverage for a real dashboard bug: room-share listings scraped
under a generic "Appartamento in affitto" title survived "Repair data"
untouched, because `is_bad_title` only recognized the sale-side placeholder
strings ("appartamento in vendita" and friends) and not their rent mirror."""
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Property
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing
from app.services.repair_listings import (
    is_bad_title,
    merge_duplicate_listings,
    repair_empty_listings_locally,
)


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


def test_merge_duplicate_listings_folds_same_url_into_one_property():
    """Regression: a re-crawl that mints a new portal_id for an ad already
    tracked (URL renumbering) slips past the portal+portal_id key in
    upsert_listing, and a surface/price mismatch keeps the geometry-based
    dedup in deduplicator.py from catching it either — producing two
    dashboard cards for the same ad. Comparing listing URLs directly is the
    only thing that still recognizes them as one property."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()

    first, is_new1, _ = upsert_listing(db, _raw(
        portal_id="111", url="https://www.immobiliare.it/annunci/111/",
        sqm=60, rooms=2,
    ))
    db.commit()
    second, is_new2, _ = upsert_listing(db, _raw(
        portal_id="222", url="https://immobiliare.it/annunci/111?utm_source=email",
        sqm=95, rooms=4,
    ))
    db.commit()

    assert is_new1 and is_new2
    assert first.id != second.id
    assert len(list(db.scalars(select(Property)))) == 2

    summary = merge_duplicate_listings(db)
    db.commit()

    assert summary["properties_merged"] == 1
    remaining = list(db.scalars(select(Property)))
    assert len(remaining) == 1
    assert len(remaining[0].listings) == 2
