"""Tests for the portal-boilerplate predicates in `services/listing_text.py`.

Regression coverage for a real dashboard bug: room-share listings scraped
under a generic "Appartamento in affitto" title were left untouched, because
`is_bad_title` only recognized the sale-side placeholder strings
("appartamento in vendita" and friends) and not their rent mirror."""

from app.services.listing_text import is_bad_title, is_placeholder_zone


def test_is_bad_title_recognizes_rent_placeholders_like_sale_ones():
    for placeholder in (
        "Appartamento in affitto",
        "In affitto a Milano, Milano",
        "Residenziale in affitto a Milano",
    ):
        assert is_bad_title(placeholder) is True
    # sale mirrors keep working
    assert is_bad_title("Appartamento in vendita") is True
    assert is_bad_title("Trilocale luminoso in Navigli") is False


def test_placeholder_zone_needs_a_real_comune_tail():
    """The geocoder skips a placeholder zone rather than asking Nominatim for
    it. The tail is what makes it recognizable — an unknown one means the text
    says something, so it is kept and looked up (fail towards keeping data)."""
    assert is_placeholder_zone("In vendita a Milano") is True
    assert is_placeholder_zone("Appartamento in affitto a Milano, Milano") is True
    # a real neighbourhood, and a phrase whose tail is not a comune
    assert is_placeholder_zone("Città Studi") is False
    assert is_placeholder_zone("In vendita a Quartiere Fantasia") is False
    # unlike a title, a bare phrase with no place tail is not a zone verdict
    assert is_placeholder_zone("Appartamento in vendita") is False
