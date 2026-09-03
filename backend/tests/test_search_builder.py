"""The search-URL grammar, in both directions.

`search_builder` decides what a scan actually asks the portals for, and until
now it was only exercised in passing from `test_features.py`. What it owns here
is the zone selection: a list on the way in, a list on the way out, and the same
list after a round trip through a portal's own URL.

Every URL below is a *string* — the grammar is what is under test, so nothing
here fetches a page or needs a portal to be reachable.
"""

import logging

import pytest

from app import schemas
from app.services.search_builder import (
    MAX_SEARCH_PARTS,
    bands_are_total,
    build_idealista_url,
    build_immobiliare_url,
    parse_drawn_area,
    parse_search_url,
    price_bands,
    segment_search,
    with_newest_first,
)

# The URL Immobiliare produces when three districts are picked on its own map.
# The selection is nowhere in the path — that stays at the bare municipality —
# and lives entirely in the repeated idMZona[] parameters, which is the whole of
# the defect this file was written for. `criterio=rilevanza` is the portal's own
# sort control, copied along with the rest: it is where the spelling the builder
# now writes was read from.
MULTI_ZONE_URL = (
    "https://www.immobiliare.it/vendita-case/milano/"
    "?idMZona[]=10046&idMZona[]=10047&idMZona[]=10048"
    "&criterio=rilevanza&prezzoMassimo=450000&superficieMinima=70"
)

# What a built search now ends with, in each portal's own spelling of "newest
# first". Written out here rather than imported from the builder: a test that
# reads the value it is checking would pass whatever the value became, and the
# point of these assertions is that a scan asks for a *stated* order.
IMMOBILIARE_NEWEST = "criterio=dataModifica&ordine=desc"
IDEALISTA_NEWEST = "ordine=pubblicazione-desc"


def test_a_multi_zone_url_parses_to_a_zone_list():
    """Reading the path alone answered "Milano" and nothing else, so the form
    showed a city with an empty zone field and the scan that came out of it ran
    against the whole municipality — the search the user built on the portal's
    map, silently widened to twenty times its size."""
    parsed = parse_search_url(MULTI_ZONE_URL)

    assert parsed["city"] == "Milano"
    assert parsed["zone_ids"] == ["10046", "10047", "10048"]
    assert parsed["max_price"] == 450000
    assert parsed["min_sqm"] == 70
    # ids without names is the normal shape of a map selection, not a failure:
    # the portal never wrote the names down, so neither does the parser.
    assert parsed["zones"] == []
    assert parsed["zone"] == ""


def test_a_multi_zone_url_survives_parse_then_rebuild():
    """The acceptance test of G.1: what the user pasted is what gets scanned.

    Rebuilding from the parsed parameters used to drop every zone, because the
    builder had nowhere to put them."""
    parsed = parse_search_url(MULTI_ZONE_URL)
    rebuilt = build_immobiliare_url(**parsed)

    assert "idMZona[]=10046" in rebuilt
    assert "idMZona[]=10047" in rebuilt
    assert "idMZona[]=10048" in rebuilt
    assert "prezzoMassimo=450000" in rebuilt

    # lossless, not merely non-empty: parsing the rebuilt URL says the same
    # thing as parsing the original one.
    assert parse_search_url(rebuilt) == parsed


def test_the_zone_ids_lead_the_query_string_in_the_order_they_were_picked():
    """The same criteria must always produce a byte-identical URL, or
    search_validator reads two spellings of one search as two searches
    (invariant 20's duplicate check normalizes values, not ordering)."""
    assert build_immobiliare_url(city="Milano", zone_ids=["10047", "10046"], max_price=450_000) == (
        "https://www.immobiliare.it/vendita-case/milano/"
        f"?idMZona[]=10047&idMZona[]=10046&prezzoMassimo=450000&{IMMOBILIARE_NEWEST}"
    )
    # the same ids in the other order are a different URL, and a repeat is not
    assert build_immobiliare_url(city="Milano", zone_ids=["10046", "10047", "10046"]) == (
        f"https://www.immobiliare.it/vendita-case/milano/?idMZona[]=10046&idMZona[]=10047&{IMMOBILIARE_NEWEST}"
    )


def test_the_indexed_spelling_of_the_zone_parameter_is_read_too():
    """Immobiliare writes its array params both ways — `fasciaPiano[]` and
    `fasciaPiano[0]` both come off the live site — so a parser that knows only
    one spelling loses the selection for half the URLs a user can paste."""
    parsed = parse_search_url(
        "https://www.immobiliare.it/vendita-case/milano/?idMZona[0]=10046&idMZona[1]=10047"
    )
    assert parsed["zone_ids"] == ["10046", "10047"]


def test_a_single_zone_path_url_still_round_trips_exactly():
    """The pretty single-zone form is what the portal emits for one district,
    and the search it describes must come back out untouched: the zone list is
    an addition, not a rewrite of the grammar that already worked. What the
    rebuilt URL gains is the ordering, which is not part of the search — it
    decides how the same listings are arranged."""
    url = "https://www.immobiliare.it/vendita-case/milano/navigli/?prezzoMassimo=380000"
    parsed = parse_search_url(url)

    assert parsed["zone"] == "Navigli"
    assert parsed["zones"] == ["Navigli"]
    assert parsed["zone_ids"] == []
    assert build_immobiliare_url(**parsed) == f"{url}&{IMMOBILIARE_NEWEST}"


def test_a_plain_city_url_still_round_trips_exactly():
    url = "https://www.immobiliare.it/affitto-case/milano/?prezzoMassimo=1500"
    parsed = parse_search_url(url)

    assert parsed["zone"] == "" and parsed["zones"] == [] and parsed["zone_ids"] == []
    assert build_immobiliare_url(**parsed) == f"{url}&{IMMOBILIARE_NEWEST}"


def test_zone_and_zones_are_one_field_at_two_arities():
    """`zone` keeps working as the first element of `zones`, in both
    directions, so nothing written before the list changes meaning."""
    from_string = build_immobiliare_url(city="Milano", zone="Navigli")
    from_list = build_immobiliare_url(city="Milano", zones=["Navigli"])
    assert (
        from_string
        == from_list
        == f"https://www.immobiliare.it/vendita-case/milano/navigli/?{IMMOBILIARE_NEWEST}"
    )

    payload = schemas.SearchBuilderIn(city="Milano", zone="Navigli")
    assert payload.zones == ["Navigli"]
    payload = schemas.SearchBuilderIn(city="Milano", zones=["Navigli", "Bovisa"])
    assert payload.zone == "Navigli"


def test_ids_decide_the_path_when_a_url_carries_both():
    """A zone slug is best-effort; an id is what the portal actually filters on.
    A path slug beside a contradicting id list is a grammar Immobiliare has
    never been observed to emit, so the ids win and the path stays at the
    municipality — exactly what the portal's own map produces."""
    url = build_immobiliare_url(city="Milano", zone="Navigli", zone_ids=["10046"])
    assert (
        url
        == f"https://www.immobiliare.it/vendita-case/milano/?idMZona[]=10046&{IMMOBILIARE_NEWEST}"
    )


def test_several_zone_names_without_ids_use_the_first_and_do_not_invent_a_grammar():
    """Immobiliare's path holds one zone and turning names into ids needs its
    live autocomplete, so a hand-typed multi-zone selection cannot be expressed
    offline. The first name is used rather than a made-up path — and saying so
    on screen is G.2's job, not this function's."""
    url = build_immobiliare_url(city="Milano", zones=["Navigli", "Bovisa"])
    assert url == f"https://www.immobiliare.it/vendita-case/milano/navigli/?{IMMOBILIARE_NEWEST}"


def test_idealista_opaque_zone_ids_are_reported_without_inventing_a_location():
    """/multi/vendita-case/aOA,aOw/ is two zones named in the portal's own
    alphabet. City and zone stay blank — a bogus city silently blocks every
    cross-portal merge (invariant 1) — but the ids themselves are real, and
    rendering nothing for a URL that plainly holds two zones is what made a
    city-wide search look like a zone search."""
    parsed = parse_search_url("https://www.idealista.it/multi/vendita-case/aOA,aOw/")

    assert parsed["city"] == "" and parsed["zone"] == "" and parsed["zones"] == []
    assert parsed["zone_ids"] == ["aOA", "aOw"]

    # a drawn polygon carries no zone at all, and must not acquire one
    drawn = parse_search_url("https://www.idealista.it/aree/vendita-case/?shape=%7B%22type%22")
    assert drawn["zone_ids"] == [] and drawn["zones"] == []


def test_the_parse_endpoint_answers_with_the_zone_list():
    """SearchBuilderParamsOut is what the form reads; a field the model does not
    carry is a field the user never sees."""
    from app.routers.searches import search_builder_parse

    out = search_builder_parse(schemas.UrlIn(url=MULTI_ZONE_URL))

    assert out.zone_ids == ["10046", "10047", "10048"]
    assert out.zones == []
    assert out.city == "Milano"


def test_a_zone_list_narrows_both_portals_or_neither():
    """Idealista's grammar takes one zone, so a list lands on its first name.
    What it must never do is quietly return the whole municipality while
    Immobiliare filters: the extra listings read as a deduplication failure
    rather than as a filter that was never applied."""
    from app.services.search_builder import build_search_urls

    urls = build_search_urls(dict(city="Milano", zones=["Navigli"], max_price=380_000))

    assert urls["immobiliare"] == (
        f"https://www.immobiliare.it/vendita-case/milano/navigli/?prezzoMassimo=380000&{IMMOBILIARE_NEWEST}"
    )
    assert urls["idealista"] == (
        f"https://www.idealista.it/cerca/vendita-case/con-prezzo_380000/Navigli_Milano/?{IDEALISTA_NEWEST}"
    )


# --- The order the results come back in -------------------------------------
#
# No search this app built ever stated one, so every search took the portal's
# default: relevance, re-ranked continuously. The ten pages the cap allows are
# then ten pages of an order that differs on every run, and a listing near the
# cut drifts in and out of the window for reasons that have nothing to do with
# the listing — arriving as a first sighting weeks after it went on sale.


def test_both_portals_are_asked_for_the_newest_listings_first():
    """The pin, in each portal's own spelling and on every URL shape a builder
    can produce. Always in the query string: Idealista answers 404 to a path
    segment it does not recognise, while an unknown query key is ignored by
    both portals — so a spelling that ages out costs the ordering and never the
    search."""
    assert build_immobiliare_url(city="Milano") == (
        f"https://www.immobiliare.it/vendita-case/milano/?{IMMOBILIARE_NEWEST}"
    )
    assert build_immobiliare_url(city="Milano", max_price=300_000).endswith(
        f"&{IMMOBILIARE_NEWEST}"
    )

    # Idealista's three grammars: the municipality page, a proven zone page,
    # and the free-text /cerca/ fallback every unproven zone lands on
    assert build_idealista_url(city="Milano").endswith(f"?{IDEALISTA_NEWEST}")
    assert build_idealista_url(city="Milano", zone="Forlanini", zone_page=True).endswith(
        f"?{IDEALISTA_NEWEST}"
    )
    assert build_idealista_url(city="Milano", zone="Bovisa").endswith(f"?{IDEALISTA_NEWEST}")


def test_a_url_that_orders_itself_keeps_the_order_it_came_with():
    """A link the user pasted is a statement of intent, not a default to
    overwrite — someone who copied a price-sorted search asked for a
    price-sorted search. Everything else gets the pin, including the profiles
    saved before there was one to get."""
    theirs = "https://www.immobiliare.it/vendita-case/milano/?criterio=prezzo&ordine=asc"
    assert with_newest_first(theirs, "immobiliare") == theirs

    plain = "https://www.immobiliare.it/vendita-case/milano/?prezzoMassimo=300000"
    assert with_newest_first(plain, "immobiliare") == f"{plain}&{IMMOBILIARE_NEWEST}"

    idealista = "https://www.idealista.it/vendita-case/milano-milano/"
    assert with_newest_first(idealista, "idealista") == f"{idealista}?{IDEALISTA_NEWEST}"
    assert (
        with_newest_first(f"{idealista}?ordine=prezzo-asc", "idealista")
        == f"{idealista}?ordine=prezzo-asc"
    )


# --- Splitting a search too big for one -------------------------------------
#
# The scanner decides *when* to split and proves the parts covered the whole
# afterwards; what is under test here is the grammar it splits along — the two
# axes that partition a search with no gap and no overlap, and the searches that
# have neither.


def test_price_bands_leave_no_gap_and_no_overlap():
    """Both failure modes are silent and only one of them loses listings, which
    is why the bands are inclusive and each floor is the previous ceiling plus
    one euro: written to share a boundary, every listing priced at exactly the
    boundary is fetched twice; written a euro apart, every one of them is lost."""
    bands = price_bands(0, 400_000, 4)

    assert bands == [(0, 99_999), (100_000, 199_999), (200_000, 299_999), (300_000, 400_000)]
    assert bands_are_total(bands, 0, 400_000)

    # and the check is not a formality: it says no to a partition that misses
    # the 100.000-149.999 slice, and to one that counts it twice
    assert not bands_are_total([(0, 99_999), (150_000, 400_000)], 0, 400_000)
    assert not bands_are_total([(0, 199_999), (100_000, 400_000)], 0, 400_000)
    # nor does it accept a partition that stops short of what was asked for
    assert not bands_are_total([(0, 99_999), (100_000, 300_000)], 0, 400_000)
    assert not bands_are_total([], 0, 400_000)


def test_a_narrow_range_is_not_split_into_more_bands_than_it_has_euros():
    assert price_bands(200_000, 200_002, 4) == []
    assert price_bands(0, 400_000, 1) == []


def test_a_zone_selection_becomes_one_search_per_zone():
    """The cheapest axis, and the exact one: `idMZona[]` values are the portal's
    own disjoint keys, so one search per zone covers the selection exactly once
    with no arithmetic to get wrong. Everything else about the URL — the price
    cap, the surface, the ordering the user pasted — travels into every part."""
    parts = segment_search(MULTI_ZONE_URL, "immobiliare", 3)

    assert len(parts) == 3
    assert [parse_search_url(p)["zone_ids"] for p in parts] == [
        ["10046"],
        ["10047"],
        ["10048"],
    ]
    assert all(parse_search_url(p)["max_price"] == 450_000 for p in parts)
    assert all(parse_search_url(p)["min_sqm"] == 70 for p in parts)
    assert all("criterio=rilevanza" in p for p in parts)


def test_more_zones_than_the_ceiling_are_grouped_down_to_it():
    """Segmenting multiplies requests and requests are what get an IP blocked,
    so a fifty-district selection is not fifty searches. Grouped, the parts
    still partition it exactly — every zone appears in exactly one group."""
    ids = [str(10_000 + n) for n in range(50)]
    url = "https://www.immobiliare.it/vendita-case/milano/?" + "&".join(
        f"idMZona[]={i}" for i in ids
    )

    parts = segment_search(url, "immobiliare", 4)

    assert len(parts) == MAX_SEARCH_PARTS
    grouped = [z for p in parts for z in parse_search_url(p)["zone_ids"]]
    assert sorted(grouped) == sorted(ids)
    assert len(grouped) == len(set(grouped))


def test_a_search_with_too_few_zones_to_split_falls_to_the_price_axis():
    """Two zones cannot make five parts, and spending two searches that still
    do not fit would buy nothing. The price axis can express five, so it is the
    one that works — and the zones stay on every part, since they are what was
    asked for and not what is being divided."""
    url = (
        "https://www.immobiliare.it/vendita-case/milano/"
        "?idMZona[]=10046&idMZona[]=10047&prezzoMassimo=500000"
    )

    parts = segment_search(url, "immobiliare", 5)

    assert len(parts) == 5
    bounds = [(parse_search_url(p)["min_price"], parse_search_url(p)["max_price"]) for p in parts]
    assert bounds[0][0] == 0 and bounds[-1][1] == 500_000
    assert bands_are_total([(low or 0, high or 0) for low, high in bounds], 0, 500_000)
    assert all(parse_search_url(p)["zone_ids"] == ["10046", "10047"] for p in parts)


def test_a_search_no_axis_can_divide_is_not_split_at_all():
    """An empty list is an answer: the caller keeps what the single search
    collected and reports it truncated, exactly as it did before this existed.

    A search with no zones and no maximum price is the shape that has neither
    axis — bands would have to invent a ceiling the user never asked for, and a
    search with a price cap nobody set is a search for something else.
    Idealista has neither axis at all: its price lives in a path segment it
    answers 404 to when the spelling is wrong, so rewriting one would be a
    guess rather than arithmetic.
    """
    open_ended = "https://www.immobiliare.it/vendita-case/milano/?prezzoMinimo=100000"
    assert segment_search(open_ended, "immobiliare", 3) == []

    assert segment_search(MULTI_ZONE_URL, "idealista", 3) == []
    assert (
        segment_search("https://www.idealista.it/vendita-case/milano-milano/", "idealista", 3) == []
    )
    # and "one part" is not a split
    assert segment_search(MULTI_ZONE_URL, "immobiliare", 1) == []


# --- the area a map URL states outright ------------------------------------
#
# Immobiliare's map tools say where to look far more exactly than a zone list
# can: `vrt` is a perimeter, `centro`+`raggio` is a circle, and the isochrone
# behind "ten minutes by car" arrives as a `vrt` polygon like any other. All
# three were already *searched* correctly — api-next is handed the query string
# whole — and none of them was ever read back, so the one search that stated its
# area exactly was the one nothing could be checked against.

# A square around the Navigli, in the portal's own spelling: "lat,lng" pairs
# joined by semicolons, which is the format `geo_filter.parse_polygon` parses.
DRAWN_SQUARE = "45.44,9.16;45.46,9.16;45.46,9.19;45.44,9.19"
DRAWN_URL = (
    f"https://www.immobiliare.it/search-list/?idContratto=1&idCategoria=1&vrt={DRAWN_SQUARE}"
)
RADIUS_URL = (
    "https://www.immobiliare.it/search-list/"
    "?idContratto=1&idCategoria=1&centro=45.4500,9.1750&raggio=1500"
)


def test_a_drawn_polygon_is_read_back_out_of_the_url():
    parsed = parse_search_url(DRAWN_URL)

    assert parsed["drawn_polygon"] == [
        (45.44, 9.16),
        (45.46, 9.16),
        (45.46, 9.19),
        (45.44, 9.19),
    ]
    assert parsed["drawn_circle"] is None
    # /search-list/ names no comune and no district, which is exactly why the
    # geometry matters: without it this URL states no area at all.
    assert parsed["city"] == "" and parsed["zone_ids"] == []


def test_a_radius_search_is_read_back_as_a_circle():
    """`centro` and `raggio` need no translation: metres are what
    `geo_filter.point_in_any` already measures a circle in."""
    parsed = parse_search_url(RADIUS_URL)

    assert parsed["drawn_circle"] == (45.45, 9.175, 1500.0)
    assert parsed["drawn_polygon"] is None


def test_an_ordinary_url_draws_nothing():
    """The common case stays quiet — no geometry, and no complaint about its
    absence."""
    parsed = parse_search_url(MULTI_ZONE_URL)

    assert parsed["drawn_polygon"] is None and parsed["drawn_circle"] is None
    # every portal answers the same dict shape, so a caller reads one of them
    idealista = parse_search_url("https://www.idealista.it/vendita-case/milano-milano/")
    assert idealista["drawn_polygon"] is None and idealista["drawn_circle"] is None
    assert parse_search_url("u")["drawn_polygon"] is None


@pytest.mark.parametrize(
    "query",
    [
        "vrt=45.44,9.16;45.46",  # two vertices short of a polygon
        "vrt=45.44,9.16,7;45.46,9.16;45.46,9.19",  # three numbers in a vertex
        "vrt=nord-ovest;45.46,9.16;45.46,9.19",  # not numbers at all
        "vrt=145.44,9.16;45.46,9.16;45.46,9.19",  # a latitude that cannot exist
        "centro=45.45,9.17",  # a centre with no radius
        "raggio=1500",  # a radius with no centre
        "centro=45.45,9.17&raggio=molto",  # a radius that is not a number
        "centro=45.45,9.17&raggio=0",  # a circle containing nothing
    ],
)
def test_an_unreadable_area_is_refused_and_not_read_as_no_area(query):
    """The reader raises rather than shrugging, because both ways of shrugging
    are worse. "No area" makes the check give up on the most exact search there
    is; an *empty* area makes it accuse every listing that came back."""
    with pytest.raises(ValueError):
        parse_drawn_area(query)


def test_an_unreadable_area_is_logged_and_never_becomes_an_empty_one(caplog):
    """What the refusal above means one level up. `parse_search_url` feeds the
    profile list and the builder form, so it may not raise — but it may not
    quietly answer "empty" either: `polygon` and `circle` come back None, which
    the scan reads as "cannot tell"."""
    broken = "https://www.immobiliare.it/search-list/?idContratto=1&vrt=45.44,9.16"

    with caplog.at_level(logging.ERROR):
        parsed = parse_search_url(broken)

    assert parsed["drawn_polygon"] is None and parsed["drawn_circle"] is None
    assert parsed["contract"] == "sale"  # the rest of the URL still parses
    assert "cannot be read" in caplog.text


def test_reading_the_area_does_not_change_what_the_portal_is_asked():
    """The whole task is a check, added beside a search that already works. A
    /search-list/ URL is handed to api-next as it arrived — geometry included,
    because the portal owns the geometry — and this must not have touched a
    single parameter of it."""
    from app.scrapers.immobiliare import ImmobiliareScraper

    params = ImmobiliareScraper()._api_params(DRAWN_URL)

    assert params is not None
    assert params["vrt"] == DRAWN_SQUARE
    assert params["idContratto"] == "1"
    assert params["idCategoria"] == "1"
    assert params["path"] == "/search-list/"

    radius = ImmobiliareScraper()._api_params(RADIUS_URL)
    assert radius is not None
    assert radius["centro"] == "45.4500,9.1750"
    assert radius["raggio"] == "1500"
