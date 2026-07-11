from app.services.filter_engine import find_excluded_keyword, parse_keywords_csv

KEYWORDS = ["nuda proprietà", "piano terra", "seminterrato", "asta"]


def test_excludes_nuda_proprieta():
    texts = ["Trilocale luminoso", "Vendesi NUDA PROPRIETÀ di appartamento"]
    assert find_excluded_keyword(texts, KEYWORDS) == "nuda proprietà"


def test_excludes_nuda_proprieta_without_accent():
    texts = ["Vendesi nuda proprieta in centro"]
    assert find_excluded_keyword(texts, KEYWORDS) == "nuda proprietà"


def test_excludes_piano_terra():
    texts = ["Bilocale al piano terra con giardino"]
    assert find_excluded_keyword(texts, KEYWORDS) == "piano terra"


def test_clean_ad_passes():
    texts = ["Attico panoramico al quinto piano, ristrutturato"]
    assert find_excluded_keyword(texts, KEYWORDS) is None


def test_asta_does_not_discard_words_containing_it():
    """Regression: "Castanese" (a neighborhood in Milan) and "vasta" contain "asta"."""
    assert find_excluded_keyword(["Zona Castanese, ottima posizione"], KEYWORDS) is None
    assert find_excluded_keyword(["Appartamento con vasta metratura"], KEYWORDS) is None
    assert find_excluded_keyword(["Sovrastante il parco"], KEYWORDS) is None


def test_asta_as_whole_word_discards():
    assert find_excluded_keyword(["Immobile in vendita all'asta"], KEYWORDS) == "asta"
    assert find_excluded_keyword(["Asta giudiziaria del tribunale"], KEYWORDS) == "asta"


def test_piano_terra_tolerates_multiple_whitespaces():
    assert find_excluded_keyword(["bilocale al piano  terra"], KEYWORDS) == "piano terra"


def test_piano_terrazzato_is_not_discarded():
    assert find_excluded_keyword(["piano terrazzato panoramico"], KEYWORDS) is None


def test_handles_none_and_empty_texts():
    assert find_excluded_keyword(["", None], KEYWORDS) is None


def test_parse_keywords_csv():
    assert parse_keywords_csv(" asta , piano terra ,,") == ["asta", "piano terra"]
    assert parse_keywords_csv("") == []
