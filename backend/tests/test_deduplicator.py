from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.scrapers.base import RawListing
from app.services.deduplicator import street_and_civic, upsert_listing


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


def _raw(**kwargs) -> RawListing:
    base: dict[str, Any] = dict(
        portal="immobiliare", portal_id="111",
        url="https://www.immobiliare.it/annunci/111/",
        title="Trilocale via Roma", city="Milano", rooms=3, sqm=90.0,
        price=300_000.0, latitude=45.4642, longitude=9.19,
        address="Via Roma, 12",
    )
    base.update(kwargs)
    return RawListing(**base)


# --- Correct merges --------------------------------------------------------

def test_same_property_from_two_portals_is_merged(db):
    prop1, new1, _ = upsert_listing(db, _raw())
    # same property on Idealista: different agency, no coordinates,
    # but same street + house number and compatible data
    prop2, new2, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        url="https://www.idealista.it/immobile/999/",
        price=310_000.0, sqm=92.0, latitude=None, longitude=None,
        address="via roma, 12",
    ))
    assert new1 is True
    assert new2 is False, "second listing must be merged into the same property"
    assert prop1.id == prop2.id
    assert len(prop2.listings) == 2
    assert prop2.current_min_price == 300_000.0


def test_match_by_coordinates_without_address(db):
    prop1, _, _ = upsert_listing(db, _raw(address=""))
    prop2, new2, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", address="",
        latitude=45.46425, longitude=9.19012,  # ~10 m distance
    ))
    assert new2 is False
    assert prop1.id == prop2.id


# --- Protections against false merges (regressions from real data) ---------

def test_same_street_different_civic_is_not_merged(db):
    upsert_listing(db, _raw(address="Via Roma, 12", latitude=None, longitude=None))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        address="Via Roma, 88", latitude=None, longitude=None,
    ))
    assert is_new is True


def test_without_location_proof_is_not_merged(db):
    """Regression: in a large city, many 90 sqm three-room apartments cost ~300k.
    Without coordinates or street+civic, we cannot conclude they are the same."""
    upsert_listing(db, _raw(latitude=None, longitude=None, address=""))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        latitude=None, longitude=None, address="",
        price=305_000.0,  # within ±5%
    ))
    assert is_new is True


def test_address_without_civic_is_not_enough(db):
    upsert_listing(db, _raw(address="Via Ornato", latitude=None, longitude=None))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        address="Via Ornato", latitude=None, longitude=None,
    ))
    assert is_new is True


def test_price_too_different_is_not_merged(db):
    """Regression: 416,000 € and 499,000 € are not the same apartment
    even if street, civic, rooms, and square meters match."""
    upsert_listing(db, _raw(price=499_000.0))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", price=416_000.0,
    ))
    assert is_new is True


def test_without_price_is_not_merged(db):
    """Regression: 10 studio apartments of 40 sqm in the same building, all without
    price, were previously merged into a single card."""
    upsert_listing(db, _raw(portal="idealista", portal_id="1", price=None,
                            sqm=40.0, rooms=1))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="2", price=None, sqm=40.0, rooms=1,
    ))
    assert is_new is True


def test_different_floors_are_not_merged(db):
    upsert_listing(db, _raw(floor="2"))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", floor="5",
    ))
    assert is_new is True


def test_different_rooms_are_not_merged(db):
    upsert_listing(db, _raw(rooms=3))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", rooms=2,
    ))
    assert is_new is True


def test_sqm_too_different_is_not_merged(db):
    upsert_listing(db, _raw(sqm=90.0))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", sqm=110.0,
    ))
    assert is_new is True


def test_distant_properties_remain_separate(db):
    prop1, _, _ = upsert_listing(db, _raw(address=""))
    prop2, new2, _ = upsert_listing(db, _raw(
        portal_id="222", url="https://www.immobiliare.it/annunci/222/",
        latitude=45.50, longitude=9.25, address="",  # ~5 km distance
        rooms=2, sqm=55.0, price=180_000.0,
    ))
    assert new2 is True
    assert prop1.id != prop2.id


def test_different_cities_are_not_merged(db):
    upsert_listing(db, _raw(city="Milano", latitude=None, longitude=None))
    _, is_new, _ = upsert_listing(db, _raw(
        portal="idealista", portal_id="999",
        city="Torino", latitude=None, longitude=None,
    ))
    assert is_new is True


# --- Price history ---------------------------------------------------------

def test_revisiting_same_listing_updates_price_and_history(db):
    prop, _, _ = upsert_listing(db, _raw())
    prop2, is_new, price_changed = upsert_listing(db, _raw(price=285_000.0))
    assert is_new is False
    assert price_changed is True
    assert prop2.current_min_price == 285_000.0
    assert prop2.first_price == 300_000.0
    assert len(prop2.price_history) == 1
    assert prop2.price_history[0].old_price == 300_000.0
    assert prop2.price_history[0].new_price == 285_000.0


def test_variation_on_non_minimum_listing_does_not_signal_price_change(db):
    """The price "of the house" is the minimum among merged listings: if only
    the most expensive listing changes, the minimum does not change and nothing
    should be notified.
    Regression: notified by reading an old history row."""
    upsert_listing(db, _raw(price=300_000.0))
    upsert_listing(db, _raw(
        portal="idealista", portal_id="999", price=310_000.0,
    ))
    # the most expensive portal drops to 305k: minimum stays 300k
    prop, _, price_changed = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", price=305_000.0,
    ))
    assert price_changed is False
    assert prop.current_min_price == 300_000.0
    assert prop.price_history == []


def test_cheaper_twin_listing_lowers_minimum(db):
    """Finding the same house cheaper on another portal is a price change
    to all intents and purposes ("costs less elsewhere")."""
    upsert_listing(db, _raw(price=300_000.0))
    prop, is_new, price_changed = upsert_listing(db, _raw(
        portal="idealista", portal_id="999", price=290_000.0,
    ))
    assert is_new is False
    assert price_changed is True
    assert prop.current_min_price == 290_000.0
    assert prop.price_history[-1].old_price == 300_000.0
    assert prop.price_history[-1].new_price == 290_000.0


# --- Address normalization -------------------------------------------------

def test_street_and_civic():
    assert street_and_civic("Via Val Gardena, 17") == ("via val gardena", "17")
    assert street_and_civic("corso  Lodi , 34") == ("corso lodi", "34")
    # accents and uppercase should not matter
    assert street_and_civic("Viale Città Studi, 5") == street_and_civic("viale citta studi 5")
    # without house number, it is not location proof
    assert street_and_civic("Via Ornato") is None
    assert street_and_civic("") is None
