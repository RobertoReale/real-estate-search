"""Portal scraper registry and URL detection utilities.

Provides a unified factory to instantiate the appropriate scraper instance
and detect the target portal from a search URL.
"""

from .idealista import IdealistaScraper
from .immobiliare import ImmobiliareScraper


def get_scraper(portal: str):
    """Instantiate and return the scraper corresponding to the given portal name."""
    if portal == "immobiliare":
        return ImmobiliareScraper()
    if portal == "idealista":
        return IdealistaScraper()
    raise ValueError(f"Unsupported portal: {portal}")


def detect_portal(url: str) -> str:
    """Identify the portal ('immobiliare' or 'idealista') from a listing or search URL."""
    if "immobiliare.it" in url:
        return "immobiliare"
    if "idealista.it" in url:
        return "idealista"
    raise ValueError("Unrecognized URL: must be from immobiliare.it or idealista.it")
