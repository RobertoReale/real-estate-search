"""Tests for the "Repair data" maintenance action.

Regression coverage for a real dashboard bug: room-share listings scraped
under a generic "Appartamento in affitto" title survived "Repair data"
untouched, because `is_bad_title` only recognized the sale-side placeholder
strings ("appartamento in vendita" and friends) and not their rent mirror."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PriceHistory, Property
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing
from app.services.repair_listings import (
    is_bad_title,
    merge_duplicate_listings,
    repair_empty_listings_locally,
)


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


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


def test_repair_is_idempotent_and_never_appends_the_city_twice():
    """Regression: with an empty zone and a *good* title, every repair run
    used to rewrite the title because _extract_zone_and_title returned it
    with the city appended and "different from before" was treated as an
    improvement — "Attico, Via Roma 5" became "Attico, Via Roma 5, Milano",
    then "…, Milano, Milano" on the next run, and so on forever."""
    db = _db()
    prop = upsert_listing(db, _raw(
        title="Attico, Via Roma 5", zone="", contract="sale",
    ))[0]
    db.commit()

    repair_empty_listings_locally(db)
    db.refresh(prop)
    first_pass_title = prop.title

    repair_empty_listings_locally(db)
    db.refresh(prop)
    assert prop.title == first_pass_title
    assert prop.title.count("Milano") <= 1


def test_merge_that_revives_a_gone_survivor_clears_gone_at():
    """Regression: when the duplicate's status won ("active" beats "gone"),
    the merge copied the status but left `gone_at` set — market_velocity reads
    `gone_at is not None` before the current status, so the revived property
    kept reporting a truncated, bogus days-on-market."""
    db = _db()
    survivor = upsert_listing(db, _raw(
        portal_id="111", url="https://www.immobiliare.it/annunci/111/",
        sqm=60, rooms=2,
    ))[0]
    db.commit()
    upsert_listing(db, _raw(
        portal_id="222", url="https://immobiliare.it/annunci/111/",
        sqm=95, rooms=4,
    ))
    db.commit()

    survivor.status = "gone"
    survivor.gone_at = datetime.now(timezone.utc)
    db.commit()

    merge_duplicate_listings(db)
    db.commit()

    remaining = list(db.scalars(select(Property)))
    assert len(remaining) == 1
    assert remaining[0].status == "active"
    assert remaining[0].gone_at is None


def test_merge_that_lowers_the_minimum_records_price_history():
    """Regression: the merge set current_min_price directly, bypassing
    _refresh_min_price — no PriceHistory row was written even when the merge
    genuinely lowered the price, breaking the "price_history[-1] is the last
    recorded change" contract the notifier and trend charts rely on."""
    db = _db()
    survivor = upsert_listing(db, _raw(
        portal_id="111", url="https://www.immobiliare.it/annunci/111/",
        sqm=60, rooms=2, price=1200.0,
    ))[0]
    db.commit()
    upsert_listing(db, _raw(
        portal_id="222", url="https://immobiliare.it/annunci/111/",
        sqm=95, rooms=4, price=1000.0,
    ))
    db.commit()

    merge_duplicate_listings(db)
    db.commit()

    db.refresh(survivor)
    assert survivor.current_min_price == 1000.0
    history = list(db.scalars(select(PriceHistory)))
    assert history, "the lowered minimum must be recorded in price history"
    assert history[-1].old_price == 1200.0
    assert history[-1].new_price == 1000.0
