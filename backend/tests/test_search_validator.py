import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import schemas
from app.database import Base
from app.main import create_profile, update_profile
from app.models import SearchProfile
from app.services.search_validator import (
    check_duplicate_profile,
    deduplicate_search_profiles,
    normalize_profile_keywords,
    normalize_profile_url,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_normalize_profile_url():
    url1 = "https://www.idealista.it/vendita-case/milano/con-ascensore/con-prezzo_260000,dimensione_50/"
    url2 = (
        "HTTPS://WWW.IDEALISTA.IT/vendita-case/milano/con-ascensore/con-prezzo_260000,dimensione_50"
    )
    assert normalize_profile_url(url1) == normalize_profile_url(url2)

    imm1 = "https://www.immobiliare.it/search-list/?idCategoria=1&idContratto=1&id=181029720&imm_source=bookmarkricerche&pag=1"
    imm2 = "https://www.immobiliare.it/search-list/?idContratto=1&idCategoria=1"
    assert normalize_profile_url(imm1) == normalize_profile_url(imm2)


def test_normalize_profile_keywords():
    assert normalize_profile_keywords("box, garage, Terrazzo") == "box,garage,terrazzo"
    assert normalize_profile_keywords("garage,  terrazzo, BOX , box ") == "box,garage,terrazzo"
    assert normalize_profile_keywords("") == ""


def test_check_duplicate_profile(db):
    p1 = SearchProfile(
        name="Milano Est",
        portal="idealista",
        search_url="https://www.idealista.it/vendita-case/milano/est/",
        excluded_keywords="box, garage",
    )
    db.add(p1)
    db.commit()

    # Exact duplicate URL and keywords (different order/case)
    dup = check_duplicate_profile(
        db,
        "https://www.idealista.it/vendita-case/milano/est",
        "GARAGE, box ",
    )
    assert dup is not None
    assert dup.id == p1.id

    # Exclude self ID
    assert (
        check_duplicate_profile(
            db,
            "https://www.idealista.it/vendita-case/milano/est",
            "garage, box",
            exclude_profile_id=p1.id,
        )
        is None
    )

    # Different keywords -> not a duplicate
    assert (
        check_duplicate_profile(
            db,
            "https://www.idealista.it/vendita-case/milano/est",
            "terrazzo",
        )
        is None
    )


def test_deduplicate_search_profiles(db):
    p1 = SearchProfile(
        name="Bicocca 1",
        portal="idealista",
        search_url="https://www.idealista.it/vendita-case/milano/bicocca/",
        excluded_keywords="",
    )
    p2 = SearchProfile(
        name="Bicocca 2",
        portal="idealista",
        search_url="https://www.idealista.it/vendita-case/milano/bicocca",
        excluded_keywords=" ",
    )
    db.add_all([p1, p2])
    db.commit()

    removed = deduplicate_search_profiles(db)
    assert removed == 1

    remaining = list(db.scalars(select(SearchProfile)))
    assert len(remaining) == 1
    assert remaining[0].name == "Bicocca 1"


def test_api_create_and_update_duplicate_prevention(db):
    payload = schemas.SearchProfileIn(
        name="Navigli",
        search_url="https://www.idealista.it/vendita-case/milano/navigli/",
        excluded_keywords="asta",
        notify_channels="",
        is_active=True,
    )
    r1 = create_profile(payload, db=db)
    assert r1.name == "Navigli"

    # Try creating identical profile
    with pytest.raises(HTTPException) as exc_info:
        create_profile(payload, db=db)
    assert exc_info.value.status_code == 400
    assert "An identical monitored search already exists" in exc_info.value.detail

    # Create another different profile
    payload2 = schemas.SearchProfileIn(
        name="Bovisa",
        search_url="https://www.idealista.it/vendita-case/milano/bovisa/",
        excluded_keywords="asta",
        notify_channels="",
        is_active=True,
    )
    r3 = create_profile(payload2, db=db)
    assert r3.name == "Bovisa"
    bovisa_id = r3.id

    # Try updating Bovisa to match Navigli
    with pytest.raises(HTTPException) as exc_info2:
        update_profile(bovisa_id, payload, db=db)
    assert exc_info2.value.status_code == 400
    assert "An identical monitored search already exists" in exc_info2.value.detail
