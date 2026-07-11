"""Maintenance module to repair empty or incomplete properties and imported listings.

When properties were imported via email prior to extraction enhancements, they
often lacked `city`, `zone`, `image_url`, and descriptive `title`. This service
analyzes existing database text (email subjects, URLs, titles, search profiles)
to instantly populate missing fields without requiring external web visits.
"""
import logging
import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Property, Listing, ImportedListing, SearchProfile

logger = logging.getLogger(__name__)

KNOWN_CITIES = [
    "Milano", "Roma", "Torino", "Bologna", "Firenze", "Napoli", "Genova",
    "Palermo", "Bari", "Catania", "Verona", "Padova", "Trieste", "Brescia",
    "Parma", "Taranto", "Modena", "Reggio Calabria", "Reggio Emilia",
    "Perugia", "Livorno", "Ravenna", "Cagliari", "Foggia", "Rimini",
    "Salerno", "Ferrara", "Latina", "Giugliano in Campania", "Monza",
    "Siracusa", "Pescara", "Bergamo", "Forlì", "Trento", "Vicenza",
    "Terni", "Bolzano", "Novara", "Piacenza", "Ancona", "Andria",
    "Arezzo", "Udine", "Cesena", "Lecce", "Pesaro", "Barletta",
    "Alessandria", "La Spezia", "Pistoia", "Pisa", "Catanzaro", "Lucca",
    "Brindisi", "Treviso", "Como", "Busto Arsizio", "Varese",
    "Sesto San Giovanni", "Pozzuoli", "Casoria", "Cinisello Balsamo",
    "Gela", "Cremona", "Pavia", "Imola", "Cellio con Breia"
]


def _detect_city(text: str) -> str:
    if not text:
        return ""
    text_clean = text.replace("_", " ").replace("-", " ")
    for city in KNOWN_CITIES:
        if re.search(r"\b" + re.escape(city) + r"\b", text_clean, re.I):
            return city
    return ""


def is_bad_title(title: str) -> bool:
    if not title:
        return True
    tl = title.casefold().strip(" .-")
    if tl in ("appartamento in vendita", "n/a", "", "in vendita a milano, milano", "vendita a milano, milano", "residenziale in vendita a milano, milano", "residenziale in vendita a milano", "immobile residenziale in vendita"):
        return True
    if any(k in tl for k in ("ti propone un immobile", "ti propone:", "affiliato ", "gabetti ", "tempocasa ", "studio quattro", "strategie immobiliari", "dhome real estate", "cosetta fiori")):
        return True
    return False


def _extract_zone_and_title(subject: str, city: str, orig_title: str) -> tuple[str, str]:
    raw = subject if subject and len(subject) > len(orig_title) else (orig_title or subject or "")
    # Remove agency / alert email prefixes
    cleaned = re.sub(r"^(?:Affiliato\s+[^:]+|Gabetti\s+[^:]+|TEMPOCASA\s+[^:]+|STUDIO\s+[^:]+|Strategie\s+Immobiliari\s*|Dhome\s+Real\s+Estate\s*|Cosetta\s+Fiori\s*):\s*", "", raw, flags=re.I)
    cleaned = re.sub(r"\b(?:ti propone un immobile per la tua ricerca\s*:?|ti propone\s*:?|\s+:\s+Residenziale in vendita)\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\|\s*(?:Immobiliare\.it|Idealista|Casa\.it).*$", "", cleaned, flags=re.I)
    
    lines = [l.strip() for l in re.split(r"[\r\n]+", cleaned) if l.strip()]
    detail = lines[-1] if lines else cleaned
    detail = " ".join(detail.split()).strip(" :-")
    
    zone = ""
    title = orig_title
    if detail and detail.casefold() not in ("appartamento in vendita", "residenziale in vendita a milano", "residenziale in affitto a milano", "in vendita a milano", "vendita a milano"):
        parts = [p.strip() for p in re.split(r"[-–—]", detail) if p.strip()]
        if len(parts) >= 2:
            if any(w in parts[-1].casefold() for w in ("locale", "attico", "villa", "loft", "casa", "appartamento")):
                zone = parts[0]
                title = f"{parts[-1]} - {parts[0]}, {city or 'Italia'}"
            elif any(w in parts[0].casefold() for w in ("locale", "attico", "villa", "loft", "casa", "appartamento")):
                zone = parts[-1]
                title = f"{parts[0]} - {parts[-1]}, {city or 'Italia'}"
            else:
                title = f"{detail}, {city or 'Italia'}"
        else:
            title = f"{detail}, {city or 'Italia'}"
            
    if is_bad_title(title):
        title = f"Immobile residenziale - {zone or city or 'Milano'}"
        
    return zone[:100], title[:150]


def repair_empty_listings_locally(db: Session) -> dict:
    """Repairs all properties and listings currently lacking city, zone, title, or image_url."""
    summary = {"properties_fixed": 0, "listings_fixed": 0, "images_recovered": 0}
    
    default_city = ""
    profiles = list(db.scalars(select(SearchProfile).where(SearchProfile.is_active == True)))
    if profiles:
        for p in profiles:
            c = _detect_city(p.search_url or p.name)
            if c:
                default_city = c
                break

    properties = list(db.scalars(select(Property)))
    for prop in properties:
        changed = False
        
        imp = db.scalar(select(ImportedListing).where(ImportedListing.property_id == prop.id))
        
        # 1. Recover city
        if not prop.city or prop.city == "N/A" or prop.city == "":
            c = ""
            for listing in prop.listings:
                c = _detect_city(listing.description or "") or _detect_city(listing.url or "")
                if c:
                    break
            if not c and imp:
                c = _detect_city(imp.email_subject or "") or _detect_city(imp.title or "")
            if not c:
                c = default_city
            if c:
                prop.city = c
                changed = True

        # 2. Recover zone & title
        if is_bad_title(prop.title) or not prop.zone or prop.zone == "" or prop.zone.casefold() in ("in vendita a milano", "vendita a milano"):
            subj = imp.email_subject if imp else ""
            zone, new_title = _extract_zone_and_title(subj, prop.city, prop.title)
            if zone and (not prop.zone or prop.zone.casefold() in ("in vendita a milano", "vendita a milano", "")):
                prop.zone = zone
                changed = True
            elif prop.zone and prop.zone.casefold() in ("in vendita a milano", "vendita a milano"):
                prop.zone = ""
                changed = True
            if new_title and (is_bad_title(prop.title) or new_title != prop.title):
                if not is_bad_title(new_title):
                    prop.title = new_title
                    changed = True
                elif is_bad_title(prop.title):
                    prop.title = f"Immobile residenziale - {prop.zone or prop.city or 'Milano'}"
                    changed = True

        # 3. Recover image_url across property, listings, and imported_listings
        for listing in prop.listings:
            l_changed = False
            if not prop.image_url and listing.image_url:
                prop.image_url = listing.image_url
                changed = True
                summary["images_recovered"] += 1
            elif not listing.image_url and prop.image_url:
                listing.image_url = prop.image_url
                l_changed = True
            elif not prop.image_url and imp and imp.image_url:
                prop.image_url = imp.image_url
                listing.image_url = imp.image_url
                changed = True
                l_changed = True
                summary["images_recovered"] += 1

            if l_changed:
                summary["listings_fixed"] += 1

        if changed:
            summary["properties_fixed"] += 1

    db.commit()
    logger.info("repair_empty_listings_locally completed: %s", summary)
    return summary
