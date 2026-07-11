from .immobiliare import ImmobiliareScraper
from .idealista import IdealistaScraper


def get_scraper(portal: str):
    if portal == "immobiliare":
        return ImmobiliareScraper()
    if portal == "idealista":
        return IdealistaScraper()
    raise ValueError(f"Unsupported portal: {portal}")


def detect_portal(url: str) -> str:
    if "immobiliare.it" in url:
        return "immobiliare"
    if "idealista.it" in url:
        return "idealista"
    raise ValueError("Unrecognized URL: must be from immobiliare.it or idealista.it")
