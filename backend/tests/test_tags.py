"""Tests for user-defined property tags: freeform creation with case-insensitive
dedup, the tag filter on the grid/export, PATCH full-replace semantics, bulk
add/remove, and that deleting a Property or a Tag never leaves an orphaned
row in the property_tags association table.

Endpoint functions are called directly (like test_dashboard_management), so
the app lifespan and scheduler never start."""
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import schemas
from app.database import Base
from app.main import (
    _select_properties, bulk_properties, create_tag, delete_tag, list_tags,
    patch_property,
)
from app.models import Property, Tag, property_tags
from app.scrapers.base import RawListing
from app.services.deduplicator import upsert_listing


def list_properties(*, db, **kw):
    params: dict[str, Any] = dict(
        status="active", contract=None, city=None, min_price=None,
        max_price=None, min_sqm=None, rooms=None, only_price_drops=False,
        only_favorites=False, sort="newest",
    )
    params.update(kw)
    return _select_properties(db, **params)


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
        title="Trilocale via Roma", city="Milano", zone="Navigli",
        rooms=3, sqm=90.0, price=300_000.0,
        latitude=45.4642, longitude=9.19, address="Via Roma, 12",
    )
    base.update(kwargs)
    return RawListing(**base)


def _property(db, *, portal_id: str = "111", **kwargs) -> Property:
    """Each portal_id gets its own address/coordinates so distinct calls never
    dedup-merge into the same Property (the deduplicator matches on location
    proximity, not portal_id — see invariant 1)."""
    n = int(portal_id)
    kwargs.setdefault("address", f"Via Prova, {n}")
    kwargs.setdefault("latitude", 45.4642 + n * 0.01)
    kwargs.setdefault("longitude", 9.19 + n * 0.01)
    prop, _, _ = upsert_listing(db, _raw(portal_id=portal_id, url=f"https://www.immobiliare.it/annunci/{portal_id}/", **kwargs))
    return prop


# --- Creation / dedup --------------------------------------------------------

def test_create_tag_dedup_case_insensitive(db):
    a = create_tag(schemas.TagCreate(name="Con giardino"), db)
    b = create_tag(schemas.TagCreate(name="con giardino "), db)
    assert a.id == b.id
    assert db.scalar(select(Tag).where(Tag.id == a.id)) is not None
    assert len(list(db.scalars(select(Tag)))) == 1


def test_list_tags_returns_usage_count(db):
    p1 = _property(db, portal_id="1")
    p2 = _property(db, portal_id="2")
    a = create_tag(schemas.TagCreate(name="con giardino"), db)
    b = create_tag(schemas.TagCreate(name="senza ascensore"), db)
    patch_property(p1.id, schemas.PropertyPatch(tag_ids=[a.id, b.id]), db)
    patch_property(p2.id, schemas.PropertyPatch(tag_ids=[b.id]), db)

    tags = {t.id: t.count for t in list_tags(db)}
    assert tags[a.id] == 1
    assert tags[b.id] == 2


# --- PATCH full-replace semantics --------------------------------------------

def test_patch_replaces_tag_set(db):
    prop = _property(db)
    a = create_tag(schemas.TagCreate(name="a"), db)
    b = create_tag(schemas.TagCreate(name="b"), db)

    patch_property(prop.id, schemas.PropertyPatch(tag_ids=[a.id, b.id]), db)
    db.refresh(prop)
    assert {t.id for t in prop.tags} == {a.id, b.id}

    patch_property(prop.id, schemas.PropertyPatch(tag_ids=[b.id]), db)
    db.refresh(prop)
    assert {t.id for t in prop.tags} == {b.id}


def test_patch_tag_ids_none_leaves_tags_untouched(db):
    prop = _property(db)
    a = create_tag(schemas.TagCreate(name="a"), db)
    patch_property(prop.id, schemas.PropertyPatch(tag_ids=[a.id]), db)
    patch_property(prop.id, schemas.PropertyPatch(notes="hello"), db)
    db.refresh(prop)
    assert {t.id for t in prop.tags} == {a.id}


# --- Filter -------------------------------------------------------------------

def test_filter_by_tag_name_case_insensitive(db):
    tagged = _property(db, portal_id="1")
    untagged = _property(db, portal_id="2")
    tag = create_tag(schemas.TagCreate(name="Con giardino"), db)
    patch_property(tagged.id, schemas.PropertyPatch(tag_ids=[tag.id]), db)

    result = list_properties(db=db, tag="con giardino")
    ids = {p.id for p in result}
    assert tagged.id in ids
    assert untagged.id not in ids


def test_export_respects_tag_filter(db):
    from app.main import export_properties

    tagged = _property(db, portal_id="1")
    _property(db, portal_id="2")
    tag = create_tag(schemas.TagCreate(name="con giardino"), db)
    patch_property(tagged.id, schemas.PropertyPatch(tag_ids=[tag.id]), db)

    body = export_properties(
        db=db, fmt="csv", title="Property shortlist",
        status="active", contract=None, city=None, zone=None, q=None,
        source=None, profile_id=None, tag="con giardino",
        min_price=None, max_price=None, min_sqm=None, rooms=None,
        only_price_drops=False, only_favorites=False, sort="newest",
    )
    assert "Trilocale" in bytes(body.body).decode("utf-8")


# --- Bulk ---------------------------------------------------------------------

def test_bulk_add_remove_tag(db):
    p1 = _property(db, portal_id="1")
    p2 = _property(db, portal_id="2")
    tag = create_tag(schemas.TagCreate(name="a"), db)

    bulk_properties(
        schemas.PropertyBulkIn(ids=[p1.id, p2.id], action="add_tag", tag_id=tag.id),
        db,
    )
    db.refresh(p1)
    db.refresh(p2)
    assert {t.id for t in p1.tags} == {tag.id}
    assert {t.id for t in p2.tags} == {tag.id}

    bulk_properties(
        schemas.PropertyBulkIn(ids=[p1.id], action="remove_tag", tag_id=tag.id),
        db,
    )
    db.refresh(p1)
    assert p1.tags == []


# --- Cascade behavior -----------------------------------------------------------

def test_delete_property_leaves_no_orphaned_association_row(db):
    prop = _property(db)
    tag = create_tag(schemas.TagCreate(name="a"), db)
    patch_property(prop.id, schemas.PropertyPatch(tag_ids=[tag.id]), db)

    db.delete(prop)
    db.commit()

    rows = list(db.execute(
        select(property_tags).where(property_tags.c.property_id == prop.id)
    ))
    assert rows == []


def test_delete_tag_detaches_from_all_properties(db):
    p1 = _property(db, portal_id="1")
    p2 = _property(db, portal_id="2")
    tag = create_tag(schemas.TagCreate(name="a"), db)
    patch_property(p1.id, schemas.PropertyPatch(tag_ids=[tag.id]), db)
    patch_property(p2.id, schemas.PropertyPatch(tag_ids=[tag.id]), db)

    delete_tag(tag.id, db)

    db.refresh(p1)
    db.refresh(p2)
    assert p1.tags == []
    assert p2.tags == []
    assert db.get(Property, p1.id) is not None  # properties survive
    assert db.get(Tag, tag.id) is None
    assert list_tags(db) == []
