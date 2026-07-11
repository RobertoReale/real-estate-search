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


def _extract_zone_and_title(subject: str, city: str, orig_title: str) -> tuple[str, str]:
    if not subject:
        return "", orig_title
    
    lines = [line.strip() for line in re.split(r"(\r?\n|:)", subject) if line.strip() and line.strip() != ":"]
    if len(lines) >= 2 and "ti propone" in lines[0].lower():
        detail = lines[-1].strip()
        if detail and detail.lower() not in ("appartamento in vendita", "residenziale in vendita a milano", "residenziale in affitto a milano"):
            parts = [p.strip() for p in re.split(r"[-–—]", detail) if p.strip()]
            if len(parts) >= 2:
                if any(w in parts[-1].lower() for w in ("locale", "attico", "villa", "loft", "casa")):
                    zone = parts[0]
                    title = f"{parts[-1]} - {parts[0]}, {city or 'Italia'}"
                    return zone, title
                elif any(w in parts[0].lower() for w in ("locale", "attico", "villa", "loft", "casa")):
                    zone = parts[-1]
                    title = f"{parts[0]} - {parts[-1]}, {city or 'Italia'}"
                    return zone, title
            return detail[:50], f"{detail}, {city or 'Italia'}"
    
    if orig_title in ("Appartamento in vendita", "N/A", "") and subject:
        clean_subj = re.sub(r"\b(ti propone un immobile per la tua ricerca)\b", "", subject, flags=re.I).strip(" :-\r\n")
        clean_subj = " ".join(clean_subj.split())
        if clean_subj and len(clean_subj) > 5:
            return "", f"{clean_subj}, {city or 'Italia'}"[:120]
            
    return "", orig_title


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
        if prop.title in ("Appartamento in vendita", "N/A", "") or not prop.zone or prop.zone == "":
            subj = imp.email_subject if imp else ""
            zone, new_title = _extract_zone_and_title(subj, prop.city, prop.title)
            if zone and not prop.zone:
                prop.zone = zone
                changed = True
            if new_title and new_title != prop.title and prop.title in ("Appartamento in vendita", "N/A", ""):
                prop.title = new_title
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
