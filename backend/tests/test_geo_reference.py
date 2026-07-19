"""Offline comuni gazetteer (de-Milanization, plan-resilience A).

The hand-enumerated KNOWN_CITIES / KNOWN_CITY_BOXES lists silently degraded
outside Milan's orbit: a Lecce pin was accepted only because Lecce was NOT in
the box list, and a Bergamo suburb outside the ~70-name list got no city at
all. These tests pin the general path: every Italian comune resolves, the
plausibility check is centroid-based, and detection still never guesses.
"""

from app.services import geo_reference
from app.services.geo_reference import (
    city_centroid,
    detect_city,
    is_plausible_coordinate,
    load_comuni,
)


class TestIndex:
    def test_dataset_loads_and_covers_italy(self):
        index = load_comuni()
        # ~7,900 comuni; the exact number moves with ISTAT revisions
        assert len(index._by_name) > 7000

    def test_known_comuni_resolve(self):
        index = load_comuni()
        for name in ("Milano", "Lecce", "Bolzano", "Sesto San Giovanni", "Cellio con Breia"):
            assert name in index, name

    def test_everyday_variants_resolve(self):
        # official ISTAT names are "Reggio nell'Emilia" / "Reggio di Calabria",
        # but listings and URLs write the everyday form
        index = load_comuni()
        assert "Reggio Emilia" in index
        assert "reggio-calabria" in index  # hyphens normalize to spaces

    def test_accented_names_normalize(self):
        index = load_comuni()
        assert "Forlì" in index
        assert "forli" in index


class TestDetectCity:
    def test_profile_cities_win_first(self):
        assert detect_city("nuova casa a Corsico zona centro", ("Corsico",)) == "Corsico"

    def test_index_covers_cities_the_old_list_never_had(self):
        # Matera was not in KNOWN_CITIES: the old detector was blind to it
        assert detect_city("Trilocale in vendita a Matera, centro storico") == "Matera"

    def test_longest_match_wins(self):
        # "Sesto San Giovanni" must not come back as a bare "Sesto"
        assert detect_city("appartamento a Sesto San Giovanni").casefold() == "sesto san giovanni"

    def test_urls_detect_too(self):
        assert (
            detect_city("https://www.immobiliare.it/vendita-case/reggio-emilia/").casefold()
            == "reggio emilia"
        )

    def test_no_city_returns_empty_never_a_default(self):
        # NB: everyday words can BE comuni ("Terrazzo" VR, "Paese" TV) — an
        # accepted false-positive risk for a gazetteer detector, so this text
        # is chosen to contain none
        assert detect_city("bellissimo appartamento luminosissimo ristrutturato") == ""
        assert detect_city("") == ""

    def test_short_word_comuni_are_ignored_in_free_text(self):
        # "Re" (VB) and "Ne" (GE) are real comuni but match ordinary words
        # constantly; single tokens below the length floor never detect
        assert detect_city("zona re di roma, adiacenze metro").casefold() == "roma"


class TestCentroid:
    def test_known_centroids(self):
        lat, lng = city_centroid("Milano")  # type: ignore[misc]
        assert abs(lat - 45.46) < 0.2 and abs(lng - 9.19) < 0.2
        lat, lng = city_centroid("Lecce")  # type: ignore[misc]
        assert abs(lat - 40.35) < 0.2 and abs(lng - 18.17) < 0.2

    def test_ambiguous_name_answers_none(self):
        # Castro exists in both Bergamo and Lecce provinces, ~800 km apart: a
        # centroid that might be either is worse than none (fail-open)
        assert city_centroid("Castro") is None

    def test_unknown_city_answers_none(self):
        assert city_centroid("Atlantide") is None


class TestPlausibility:
    def test_pin_near_the_city_passes(self):
        assert is_plausible_coordinate(45.47, 9.19, "Milano") is True
        # the old boxes never covered Lecce or Bolzano — a valid pin there
        # passed only via the silent `return True` default
        assert is_plausible_coordinate(40.35, 18.17, "Lecce") is True
        assert is_plausible_coordinate(46.49, 11.34, "Bolzano") is True

    def test_pin_in_another_city_fails(self):
        # the real bug class: "Dergano" (Milano) geocoded to Torino
        assert is_plausible_coordinate(45.07, 7.68, "Milano") is False

    def test_outside_italy_always_fails(self):
        assert is_plausible_coordinate(48.85, 2.35, "Milano") is False  # Paris
        assert is_plausible_coordinate(48.85, 2.35, "") is False

    def test_unknown_city_degrades_to_italy_bbox(self):
        assert is_plausible_coordinate(41.9, 12.5, "Atlantide") is True
        assert is_plausible_coordinate(41.9, 12.5, "") is True

    def test_none_coordinates_fail(self):
        assert is_plausible_coordinate(None, None, "Milano") is False


class TestFailOpen:
    def test_missing_dataset_degrades_to_empty_index(self, monkeypatch, tmp_path):
        monkeypatch.setattr(geo_reference, "DATA_PATH", tmp_path / "absent.sqlite")
        load_comuni.cache_clear()
        try:
            index = load_comuni()
            assert index.lookup("Milano") == []
            # detection then leans on the caller's profile cities alone
            assert detect_city("casa a Milano", ("Milano",)) == "Milano"
            assert detect_city("casa a Milano") == ""
            # plausibility degrades to the Italy bbox
            assert is_plausible_coordinate(45.47, 9.19, "Milano") is True
        finally:
            load_comuni.cache_clear()
