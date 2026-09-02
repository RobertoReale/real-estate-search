import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import schemas
from app.database import Base
from app.models import SearchProfile
from app.routers.profiles import create_profile, update_profile
from app.scrapers.immobiliare import MAX_ZONE_IDS
from app.services.search_builder import build_search_urls
from app.services.search_validator import (
    check_duplicate_profile,
    deduplicate_search_profiles,
    normalize_profile_keywords,
    normalize_profile_url,
    zone_coverage_warnings,
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


def test_the_sort_order_is_not_part_of_the_search():
    """A sort order decides how an answer is arranged, never what is in it, so
    the same search ranked two ways is one search — the same reason `pag` is
    ignored. Counted as a filter, the day the builder started pinning
    newest-first every rebuilt URL stopped matching the profile it was rebuilt
    from, and the duplicate check went blind to it."""
    base = "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000"

    assert normalize_profile_url(base) == normalize_profile_url(
        f"{base}&criterio=dataModifica&ordine=desc"
    )
    assert normalize_profile_url(f"{base}&criterio=rilevanza") == normalize_profile_url(
        f"{base}&criterio=prezzo&ordine=asc"
    )
    # and the filters are still what decides it
    assert normalize_profile_url(base) != normalize_profile_url(
        "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=400000"
    )


def test_normalize_profile_keywords():
    assert normalize_profile_keywords("box, garage, Terrazzo") == "box,garage,terrazzo"
    assert normalize_profile_keywords("garage,  terrazzo, BOX , box ") == "box,garage,terrazzo"
    assert normalize_profile_keywords("") == ""


def test_zone_ids_are_never_a_loss():
    """Ids travel as repeated query params, all of them, so a selection made on
    the portal's map has nothing to warn about however large it is."""
    assert zone_coverage_warnings({"city": "Milano", "zone_ids": [str(i) for i in range(20)]}) == []
    assert zone_coverage_warnings({"city": "Milano", "zone": "Navigli"}) == []
    assert zone_coverage_warnings({"city": "Milano"}) == []


def test_several_zone_names_without_ids_are_reported_before_saving():
    """The URL Immobiliare's grammar can build here holds one zone in its path,
    so two of these three are simply not searched. Unsaid, the scan answers
    normally for a wider area — which is the whole defect."""
    warnings = zone_coverage_warnings(
        {"city": "Milano", "zones": ["Navigli", "Isola", "Citta Studi"]}
    )
    assert len(warnings) == 1
    assert "Navigli" in warnings[0]  # the one that IS searched, named
    assert "2" in warnings[0]  # and how many are not
    assert "map" in warnings[0]  # and the way to keep them


def test_a_selection_too_large_for_one_request_names_the_limit():
    warnings = zone_coverage_warnings(
        {"city": "Milano", "zone_ids": [str(i) for i in range(MAX_ZONE_IDS + 5)]}
    )
    assert len(warnings) == 1
    assert str(MAX_ZONE_IDS) in warnings[0]
    assert str(MAX_ZONE_IDS + 5) in warnings[0]


def test_generated_urls_carry_the_zone_warning():
    """The warning reaches the moment before the save: `build_search_urls` is
    what the form calls to generate, and it reports this beside
    `idealista_unsupported` — the same admission, for the other portal."""
    urls = build_search_urls({"city": "Milano", "zones": ["Navigli", "Isola"]})
    assert len(urls["zone_warnings"]) == 1
    assert schemas.SearchBuilderUrlsOut(**urls).zone_warnings == urls["zone_warnings"]
    # and a search that loses nothing says nothing
    assert (
        build_search_urls({"city": "Milano", "zone_ids": ["10046", "10047"]})["zone_warnings"] == []
    )


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
