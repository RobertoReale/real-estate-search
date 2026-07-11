"""Tests for the natural-language search assistant (services/query_parser.py).

The parser is deliberately deterministic (no LLM call), so every phrasing it
claims to support can be pinned here. Most of these cases are the ones that
broke a naive implementation first — each keeps its story in a comment.
"""
from app.services.query_parser import parse_query


def first(query: str) -> dict:
    """The first (often only) search alternative the parser produced."""
    return parse_query(query)["searches"][0]


def params(query: str) -> dict:
    return first(query)["params"]


# --- The roadmap's own example ----------------------------------------------

def test_roadmap_example_query():
    p = params("find a 2-bedroom rental in Milan under 1200€")
    assert p["contract"] == "rent"
    assert p["city"] == "Milano"          # English exonym -> portal spelling
    assert p["max_price"] == 1200
    assert p["min_rooms"] == 3            # 2 bedrooms + living room


def test_bedrooms_become_locali_and_the_assumption_is_stated():
    """Italian portals count *locali* (living room included), while English
    speakers count bedrooms. Translating silently would return trilocali to
    someone who asked for a bilocale, so the +1 is spelled out in `notes`."""
    result = first("2-bedroom flat in Rome")
    assert result["params"]["min_rooms"] == 3
    assert any("locali" in n for n in result["notes"])


# --- Prices ------------------------------------------------------------------

def test_surface_is_never_read_as_a_price():
    """Regression: the "m" multiplier (millions) matched the "m" of "80 m2",
    turning a surface filter into an 80,000,000 € budget."""
    p = params("bilocale a Milano almeno 80 m2")
    assert p["min_sqm"] == 80
    assert p["max_price"] is None and p["min_price"] is None


def test_room_count_is_never_read_as_a_price():
    """"3 locali" must not become a 3 € budget: bare numbers only count as
    money above 100 and when no unit word follows them."""
    p = params("appartamento 3 locali a Torino")
    assert p["min_rooms"] == 3
    assert p["max_price"] is None


def test_thousands_separators_multipliers_and_currency():
    assert params("casa a Roma sotto i 1.500 euro al mese")["max_price"] == 1500
    assert params("casa a Roma max 300k")["max_price"] == 300_000
    assert params("casa a Roma budget 250 mila")["max_price"] == 250_000
    assert params("casa a Roma fino a 1,2 mln")["max_price"] == 1_200_000


def test_explicit_range_beats_a_lone_minimum():
    """"da 200k a 300k" starts with "da", a MIN keyword: without range
    detection running first it parsed as min=200k and dropped the ceiling."""
    p = params("attico a Firenze da 400k a 600k")
    assert (p["min_price"], p["max_price"]) == (400_000, 600_000)


def test_range_is_ordered_even_when_typed_backwards():
    p = params("casa a Roma tra 300k e 200k")
    assert (p["min_price"], p["max_price"]) == (200_000, 300_000)


def test_lone_amount_is_a_ceiling_not_a_floor():
    """Nobody searches for a house costing *at least* their budget."""
    p = params("casa a Milano 300k")
    assert p["max_price"] == 300_000 and p["min_price"] is None


def test_minimum_price_keyword():
    p = params("casa a Milano almeno 200k")
    assert p["min_price"] == 200_000 and p["max_price"] is None


# --- Contract ----------------------------------------------------------------

def test_rent_detected_from_italian_and_english():
    assert params("bilocale in affitto a Milano")["contract"] == "rent"
    assert params("rental in Rome")["contract"] == "rent"
    assert params("casa a Milano 800 euro al mese")["contract"] == "rent"


def test_sale_is_the_default_but_flagged_as_an_assumption():
    result = first("trilocale a Milano 300k")
    assert result["params"]["contract"] == "sale"
    assert "assumed" in result["interpretation"][0]


def test_explicit_sale_is_not_flagged_as_assumed():
    result = first("casa in vendita a Milano")
    assert "assumed" not in result["interpretation"][0]


# --- City and province -------------------------------------------------------

def test_multiword_city_wins_over_its_prefix():
    """"reggio emilia" must not degrade into "reggio": longest match first."""
    assert params("casa a Reggio Emilia")["city"] == "Reggio Emilia"


def test_province_from_parenthesised_code():
    """Idealista needs the province for non-capital municipalities, and
    "Sesto San Giovanni (MI)" is how everyone writes it."""
    p = params("casa a Sesto San Giovanni (MI) tra 200k e 300k")
    assert p["city"] == "Sesto San Giovanni"
    assert p["province"] == "Milano"


def test_province_spelled_out():
    p = params("appartamento in provincia di Varese, budget 250 mila")
    assert p["province"] == "Varese"


def test_unknown_city_falls_back_to_capitalised_words_after_preposition():
    p = params("bilocale in affitto a Cernusco sul Naviglio")
    assert p["city"].startswith("Cernusco")


def test_missing_city_warns_instead_of_guessing():
    """A city-less portal URL answers 200 OK with all of Italy (invariant #7):
    the assistant must refuse to build URLs rather than fail silently."""
    result = first("cerco casa 120 mq")
    assert result["params"]["city"] == ""
    assert any("city" in w for w in result["warnings"])


def test_empty_query_is_not_an_error():
    result = first("   ")
    assert result["warnings"] and result["params"] == {}


# --- Rooms and surface -------------------------------------------------------

def test_italian_room_words():
    assert params("monolocale a Bologna")["min_rooms"] == 1
    assert params("bilocale a Bologna")["min_rooms"] == 2
    assert params("trilocale a Bologna")["min_rooms"] == 3


def test_exact_room_count_bounds_both_ends():
    p = params("3 locali a Milano")
    assert (p["min_rooms"], p["max_rooms"]) == (3, 3)


def test_at_least_rooms_leaves_the_upper_bound_open():
    p = params("almeno 3 locali a Milano")
    assert (p["min_rooms"], p["max_rooms"]) == (3, None)
    p = params("3+ locali a Milano")
    assert (p["min_rooms"], p["max_rooms"]) == (3, None)


def test_surface_variants():
    for text in ("80 mq", "80 m2", "80 metri quadri", "80 sqm"):
        assert params(f"casa a Milano di {text}")["min_sqm"] == 80


def test_maximum_surface_is_dropped_not_flipped_into_a_minimum():
    """Regression: the builder only knows `superficieMinima`, so "max 100 mq"
    used to be stored as min_sqm=100 — searching for the exact opposite of
    what the user asked. It must be dropped, with a warning."""
    result = first("casa a Milano max 100 mq")
    assert result["params"]["min_sqm"] is None
    assert any("Maximum surface" in w for w in result["warnings"])


def test_minimum_surface_still_parsed_next_to_a_price_ceiling():
    p = params("casa a Milano max 300k almeno 80 mq")
    assert (p["max_price"], p["min_sqm"]) == (300_000, 80)


# --- Zones ---------------------------------------------------------------------

def test_zone_extracted_and_city_kept():
    p = params("trilocale a Milano in zona Navigli sotto i 400k")
    assert p["city"] == "Milano"
    assert p["zone"] == "Navigli"
    assert p["max_price"] == 400_000


def test_multiword_zone_stops_at_price_keywords():
    p = params("bilocale a Milano zona Porta Romana max 300k")
    assert p["zone"] == "Porta Romana"
    assert p["max_price"] == 300_000


def test_zone_never_masquerades_as_the_city():
    """Regression risk: "Zona Isola" is capitalised, and the city fallback
    reads capitalised words after a preposition — without blanking the zone
    span the parser would report city="Zona Isola" instead of no city."""
    result = first("bilocale in zona Isola")
    assert result["params"]["zone"] == "Isola"
    assert result["params"]["city"] == ""
    assert any("city" in w for w in result["warnings"])


def test_zone_followed_by_city_keeps_both():
    """"zona Navigli Milano": a known city name ends the zone capture."""
    p = params("bilocale zona Navigli Milano")
    assert p["zone"] == "Navigli"
    assert p["city"] == "Milano"


def test_zone_produces_a_best_effort_note():
    result = first("trilocale a Milano zona Navigli")
    assert any("best-effort" in n for n in result["notes"])


# --- Multiple alternatives ("o" / "oppure" / "or") ----------------------------

def test_two_alternatives_with_different_zones():
    """The user's own example: two zones of the same city, one query."""
    result = parse_query(
        "cerco un bilocale a Milano in zona Navigli o un trilocale a "
        "Milano in zona Lambrate"
    )
    assert len(result["searches"]) == 2
    a, b = (s["params"] for s in result["searches"])
    assert (a["city"], a["zone"], a["min_rooms"]) == ("Milano", "Navigli", 2)
    assert (b["city"], b["zone"], b["min_rooms"]) == ("Milano", "Lambrate", 3)


def test_shared_context_is_inherited_by_the_alternative_that_omits_it():
    """"bilocale a Milano zona Isola o trilocale zona Lambrate sotto i 400k":
    the second alternative names no city — everyone reading the sentence
    knows it is still Milan, and the parser must too."""
    result = parse_query(
        "bilocale a Milano in zona Isola sotto i 400k o trilocale in zona Lambrate"
    )
    assert len(result["searches"]) == 2
    a, b = (s["params"] for s in result["searches"])
    assert b["city"] == "Milano"
    assert b["zone"] == "Lambrate"          # own zone, not inherited
    assert b["max_price"] == 400_000        # budget shared across alternatives
    assert a["zone"] == "Isola"


def test_context_inherits_backwards_too():
    """"bilocale o trilocale a Milano": the shared city sits on the SECOND
    alternative; the first must inherit it looking forward."""
    result = parse_query("bilocale o trilocale a Milano sotto i 350k")
    assert len(result["searches"]) == 2
    a, b = (s["params"] for s in result["searches"])
    assert a["city"] == b["city"] == "Milano"
    assert a["max_price"] == b["max_price"] == 350_000
    assert (a["min_rooms"], b["min_rooms"]) == (2, 3)


def test_zone_is_not_inherited_across_different_cities():
    """"trilocale a Milano zona Navigli o a Torino" must not put a Milanese
    neighborhood in Turin: location inherits as a bundle, and an alternative
    with its own city inherits no location at all."""
    result = parse_query("trilocale a Milano zona Navigli o a Torino")
    a, b = (s["params"] for s in result["searches"])
    assert (a["city"], a["zone"]) == ("Milano", "Navigli")
    assert (b["city"], b["zone"]) == ("Torino", "")
    assert b["min_rooms"] == 3              # rooms are shared context


def test_rent_contract_is_inherited():
    result = parse_query("bilocale in affitto a Milano zona Isola o trilocale zona Bicocca")
    assert all(s["params"]["contract"] == "rent" for s in result["searches"])


def test_spurious_split_is_glued_back():
    """"2 o 3 locali" is a room range, not two searches: a fragment that
    parses to nothing ("2") must merge back instead of producing a ghost
    alternative."""
    result = parse_query("appartamento 2 o 3 locali a Milano")
    assert len(result["searches"]) == 1
    assert result["searches"][0]["params"]["city"] == "Milano"


def test_identical_alternatives_collapse():
    result = parse_query("bilocale a Milano o bilocale a Milano")
    assert len(result["searches"]) == 1
