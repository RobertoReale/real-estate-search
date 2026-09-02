"""A deterministic demo corpus: the dashboard with data in it, without a scan.

An empty dashboard and a dashboard holding eighty properties are two different
programs, and only one of them can be looked at. Filling it by scanning takes
forty minutes, needs the portals to be reachable, and produces a different corpus
every time — no basis for a browser test, a screenshot, or showing the app to
someone. `seed_demo` writes the same corpus every run, covering in one go the
cases a real dashboard takes months to accumulate: both contracts, properties
gone from the market and properties hidden by hand, the same flat found on two
portals, price drops, favourites, tags, a missing photo, a missing pin, and three
monitored searches in the three health states the panel can show.

**Nothing here is real.** Every address, agency, portal id and ad URL is invented
from the word lists below; the only names taken from the world are the city and
its eight districts, since a demo of a Milan search reads as nothing at all set
in "Zone 1" through "Zone 8". No row is copied or derived from a scraped database
or from an OMI delivery. This module ships in the repository and in the release
bundle, so it is written to be read by anyone.

Deterministic in *content*, anchored in *time*: the generator is seeded, so a
given seed always produces the same properties in the same order, while every
timestamp is an offset from `now`. A corpus whose newest listing was found eight
months ago would read as an abandoned dashboard, and its days-on-market would
grow without limit. Pass `now` to pin those too.

It refuses a database that already holds anything (`DatabaseNotEmpty`): invented
listings merged into real ones cannot be told apart afterwards, and nothing
downstream could undo it.
"""

import base64
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Listing, ListingProfile, PriceHistory, Property, SearchProfile, Tag
from .deduplicator import fingerprint_for


class DatabaseNotEmpty(RuntimeError):
    """Raised instead of adding invented data to a database that holds real data."""


@dataclass(frozen=True)
class DemoSummary:
    """What a seeding run wrote, for the caller to report."""

    properties: int
    listings: int
    price_changes: int
    tags: int
    profiles: int


@dataclass(frozen=True)
class _Zone:
    """One district: where its pins fall, and what a square metre asks there.

    The two prices are the *centre* of the zone's spread — each property is drawn
    around them — so the corpus produces the same bargains and overpriced outliers
    a real one does, and the market-position badges have something to say.
    """

    name: str
    lat: float
    lng: float
    sale_sqm_price: float  # euro per m², asking
    rent_sqm_price: float  # euro per m² per month


CITY = "Milano"

ZONES = (
    _Zone("Brera", 45.4720, 9.1870, 9400, 27.0),
    _Zone("Navigli", 45.4520, 9.1750, 6300, 22.0),
    _Zone("Isola", 45.4880, 9.1880, 6600, 23.0),
    _Zone("Porta Romana", 45.4520, 9.2050, 6000, 21.0),
    _Zone("Città Studi", 45.4780, 9.2260, 4700, 18.0),
    _Zone("Lambrate", 45.4860, 9.2380, 4100, 17.0),
    _Zone("Bicocca", 45.5180, 9.2120, 3800, 16.0),
    _Zone("Affori", 45.5170, 9.1710, 3300, 14.5),
)

# Addresses are assembled from these two lists, so no address in the corpus is
# anyone's.
STREET_PREFIXES = ("Via", "Viale", "Largo", "Vicolo")
STREET_NAMES = (
    "dei Tigli Vecchi",
    "delle Fornaci Rosse",
    "dei Glicini Chiari",
    "del Molino Antico",
    "delle Anfore",
    "dei Fabbri Lombardi",
    "delle Cascine Nuove",
    "del Roseto Grande",
    "dei Passeri",
    "delle Vele Bianche",
    "dei Mandorli Alti",
    "del Portico Verde",
)

# Invented agencies. The empty string is a private seller, which the deal score
# reads differently from an agency listing.
AGENCIES = ("", "Aurora Case", "Meridiana Immobili", "Portico Immobiliare", "Nord Case")

# Half of these are the condition cues `deal_score.CONDITION_NEGATIVE` and
# `CONDITION_POSITIVE` look for, so the corpus exercises the score's adjustments
# instead of leaving every card on the plain €/m² gap. None of them is an
# excluded keyword (`config.DEFAULT_EXCLUDED_KEYWORDS`) — a demo property must
# not describe itself into the "filtered" bucket its status says it is not in.
CONDITIONS = (
    "ristrutturato",
    "da ristrutturare",
    "di recente costruzione",
    "luminoso",
    "con balcone",
    "in stabile signorile",
)
FEATURES = (
    "doppia esposizione",
    "cucina abitabile",
    "cantina di pertinenza",
    "ascensore in stabile",
    "affaccio sul cortile interno",
    "riscaldamento centralizzato",
)
CLOSINGS = (
    "Disponibile da subito.",
    "Visite su appuntamento.",
    "Trattativa riservata.",
)

# What `humanizeFloor` on the frontend knows how to render: ground, raised, a
# number, or nothing at all when the ad did not say.
FLOORS = ("T", "R", "1", "2", "3", "4", "5", "6", "")

TAG_NAMES = (
    "da vedere",
    "senza ascensore",
    "con giardino",
    "vicino alla metro",
    "prezzo trattabile",
    "seconda scelta",
)

DEFAULT_COUNT = 80
DEFAULT_SEED = 6112

# Fractions of the corpus rather than absolute counts, so `count` stays a real
# parameter. Each is drawn from its own shuffle, so a property can be hidden
# *and* favourite *and* missing its photo — which is what a real corpus looks
# like. Only "gone" and "hidden" share a draw, since a property has one status.
RENT_SHARE = 0.25
GONE_SHARE = 0.10
HIDDEN_SHARE = 0.10
MERGED_SHARE = 0.15
PRICE_HISTORY_SHARE = 0.20
FAVORITE_SHARE = 0.10
TAGGED_SHARE = 0.30
NO_IMAGE_SHARE = 0.15
NO_COORDINATES_SHARE = 0.15

# Ad URLs point at a host reserved by RFC 2606 to never resolve. A fabricated
# immobiliare.it path would be worse than useless: it would either 404 or, by
# coincidence, open somebody's real listing — and it would put the browser suite
# one careless click away from the network it is not allowed to reach.
DEMO_HOST = "demo.invalid"


def is_empty(db: Session) -> bool:
    """True when nothing this generator writes is already in the database."""
    for model in (Property, SearchProfile, Tag):
        if db.scalar(select(func.count()).select_from(model)):
            return False
    return True


def seed_demo(
    db: Session,
    *,
    count: int = DEFAULT_COUNT,
    seed: int = DEFAULT_SEED,
    now: datetime | None = None,
) -> DemoSummary:
    """Writes the corpus into an empty database and commits it.

    Raises `DatabaseNotEmpty` if anything is already there. See the module
    docstring for what the corpus contains and why it is shaped this way.
    """
    if not is_empty(db):
        raise DatabaseNotEmpty(
            "this database already holds properties, monitored searches or tags. "
            "The demo corpus is only ever written into an empty one."
        )

    now = now or datetime.now(UTC)
    rng = random.Random(seed)

    watch_sale, watch_any, watch_rent = _build_profiles(now)
    db.add_all([watch_sale, watch_any, watch_rent])
    tags = [Tag(name=name, name_normalized=name.lower(), created_at=now) for name in TAG_NAMES]
    db.add_all(tags)

    gone, hidden = _draw(rng, count, GONE_SHARE, HIDDEN_SHARE)
    (rent,) = _draw(rng, count, RENT_SHARE)
    (merged,) = _draw(rng, count, MERGED_SHARE)
    (with_history,) = _draw(rng, count, PRICE_HISTORY_SHARE)
    (favorite,) = _draw(rng, count, FAVORITE_SHARE)
    (tagged,) = _draw(rng, count, TAGGED_SHARE)
    (no_image,) = _draw(rng, count, NO_IMAGE_SHARE)
    (no_coordinates,) = _draw(rng, count, NO_COORDINATES_SHARE)

    listing_count = 0
    change_count = 0

    for i in range(count):
        zone = ZONES[i % len(ZONES)]
        contract = "rent" if i in rent else "sale"
        status = "hidden" if i in hidden else "gone" if i in gone else "active"
        first_seen, last_seen = _lifespan(rng, now, status)

        sqm = float(rng.randrange(35, 165, 5))
        rooms = _rooms_for(sqm)
        street = f"{rng.choice(STREET_PREFIXES)} {rng.choice(STREET_NAMES)}"
        condition = rng.choice(CONDITIONS)
        price = _asking_price(rng, zone, contract, sqm)
        image = "" if i in no_image else _placeholder_image(i)

        prop = Property(
            fingerprint=fingerprint_for(CITY, rooms, sqm),
            title=f"{_typology(rooms)} {condition} in {street}",
            city=CITY,
            zone=zone.name,
            address=f"{street} {rng.randint(1, 180)}",
            latitude=None if i in no_coordinates else _jitter(rng, zone.lat),
            longitude=None if i in no_coordinates else _jitter(rng, zone.lng),
            # A corpus pin stands for one the portal sent with the ad, which is
            # what most real pins are. The ones left without coordinates are the
            # other real case, and `geocoder.resolve_offline` is what turns them
            # into the third: an approximate pin, labelled as one.
            coordinate_source="" if i in no_coordinates else "portal",
            rooms=rooms,
            floor=rng.choice(FLOORS),
            sqm=sqm,
            contract=contract,
            current_min_price=price,
            first_price=price,
            image_url=image,
            status=status,
            is_favorite=i in favorite,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            # The scanner dates a disappearance at the last sighting, never at
            # the day it noticed (see `scanner._mark_vanished_properties`), or
            # every days-on-market figure would be inflated by the grace period.
            gone_at=last_seen if status == "gone" else None,
        )

        if i in with_history:
            drops = _price_drops(rng, price, contract, first_seen, last_seen)
            for old_price, new_price, changed_at in drops:
                prop.price_history.append(
                    PriceHistory(old_price=old_price, new_price=new_price, changed_at=changed_at)
                )
            # what it was asking when it arrived: the first reduction's old price
            prop.first_price = drops[0][0]
            change_count += len(drops)

        portal = "idealista" if i % 3 == 0 else "immobiliare"
        description = (
            f"{_typology(rooms)} di {int(sqm)} mq in zona {zone.name}, {CITY}. "
            f"{condition.capitalize()}, {rng.choice(FEATURES)}. {rng.choice(CLOSINGS)}"
        )
        prices = [price]
        portals = [portal]
        if i in merged:
            # The same flat relisted by a second agency, a little dearer. The
            # dashboard's price is the minimum across the listings, so the
            # property keeps the price above (deduplicator._refresh_min_price).
            portals.append("immobiliare" if portal == "idealista" else "idealista")
            prices.append(_round_price(price * rng.uniform(1.02, 1.08), contract))

        for n, (listing_portal, listing_price) in enumerate(zip(portals, prices, strict=True)):
            ad_id = f"demo-{i:04d}{'ab'[n]}"
            listing = Listing(
                portal=listing_portal,
                portal_id=ad_id,
                url=f"https://{DEMO_HOST}/{listing_portal}/{ad_id}",
                price=listing_price,
                agency=rng.choice(AGENCIES),
                description=description,
                image_url=image,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            )
            # Which search found the ad (ListingProfile). The two immobiliare
            # searches split by contract and the idealista one covers both, so
            # every listing has a finder and "delete a search with its results"
            # has provenance to read.
            if listing_portal == "idealista":
                finder = watch_any
            else:
                finder = watch_rent if contract == "rent" else watch_sale
            listing.profile_links.append(ListingProfile(profile=finder, first_seen_at=first_seen))
            prop.listings.append(listing)
            listing_count += 1

        if i in tagged:
            prop.tags.extend(rng.sample(tags, rng.randint(1, 2)))

        db.add(prop)

    db.commit()
    return DemoSummary(
        properties=count,
        listings=listing_count,
        price_changes=change_count,
        tags=len(tags),
        profiles=3,
    )


def _build_profiles(now: datetime) -> tuple[SearchProfile, SearchProfile, SearchProfile]:
    """Three monitored searches, one per health state the panel can show:
    running normally, blocked long enough to have alerted, and switched off.

    Their URLs are on the unresolvable demo host like the ads': a plausible
    portal search URL would send a "Scan now" on demo data to a real portal, on
    the residential IP the real scans depend on.
    """
    healthy = SearchProfile(
        name="Trilocali in vendita, Navigli e Isola",
        portal="immobiliare",
        search_url=f"https://{DEMO_HOST}/immobiliare/milano/vendita?locali=3",
        excluded_keywords="mansarda",
        is_active=True,
        baseline_done=True,
        last_run_at=now - timedelta(minutes=25),
        last_run_status="ok",
        last_run_detail="18 listings, 2 new",
        consecutive_failures=0,
        created_at=now - timedelta(days=124),
    )
    blocked = SearchProfile(
        name="Milano, tutte le zone",
        portal="idealista",
        search_url=f"https://{DEMO_HOST}/idealista/milano",
        is_active=True,
        baseline_done=True,
        last_run_at=now - timedelta(minutes=40),
        last_run_status="blocked",
        last_run_detail="the portal answered 403",
        consecutive_failures=4,
        health_alert_sent=True,
        created_at=now - timedelta(days=97),
    )
    paused = SearchProfile(
        name="Bilocali in affitto, Porta Romana",
        portal="immobiliare",
        search_url=f"https://{DEMO_HOST}/immobiliare/milano/affitto?locali=2",
        is_active=False,
        baseline_done=True,
        last_run_at=now - timedelta(days=11),
        last_run_status="ok",
        last_run_detail="9 listings",
        consecutive_failures=0,
        created_at=now - timedelta(days=61),
    )
    return healthy, blocked, paused


def _draw(rng: random.Random, count: int, *shares: float) -> list[set[int]]:
    """Splits `count` indexes into one disjoint set per share, at random.

    Every share is rounded up to at least one index, so a corpus generated with a
    small `count` still covers each case rather than dropping it silently.
    """
    indexes = list(range(count))
    rng.shuffle(indexes)
    out: list[set[int]] = []
    start = 0
    for share in shares:
        size = max(1, round(count * share))
        out.append(set(indexes[start : start + size]))
        start += size
    return out


def _rooms_for(sqm: float) -> int:
    for limit, rooms in ((45, 1), (70, 2), (95, 3), (125, 4)):
        if sqm < limit:
            return rooms
    return 5


def _typology(rooms: int) -> str:
    names = ("Monolocale", "Bilocale", "Trilocale", "Quadrilocale")
    return names[rooms - 1] if rooms <= len(names) else f"Appartamento {rooms} locali"


def _round_price(value: float, contract: str) -> float:
    """Asking prices are round: thousands for a sale, tens for a monthly rent."""
    step = 1000 if contract == "sale" else 10
    return float(round(value / step) * step)


def _asking_price(rng: random.Random, zone: _Zone, contract: str, sqm: float) -> float:
    base = zone.sale_sqm_price if contract == "sale" else zone.rent_sqm_price
    return _round_price(sqm * base * rng.uniform(0.78, 1.28), contract)


def _price_drops(
    rng: random.Random,
    price: float,
    contract: str,
    first_seen: datetime,
    last_seen: datetime,
) -> list[tuple[float, float, datetime]]:
    """One to three reductions ending at `price`, oldest first.

    Built backwards from where the property is now, so the chain always lands on
    the current minimum: a history whose last `new_price` disagreed with
    `current_min_price` would be a state no scan can produce.
    """
    steps = rng.randint(1, 3)
    ladder = [price]
    for _ in range(steps):
        ladder.append(_round_price(ladder[-1] * rng.uniform(1.03, 1.12), contract))
    ladder.reverse()
    span = (last_seen - first_seen) / (steps + 1)
    return [(ladder[n], ladder[n + 1], first_seen + span * (n + 1)) for n in range(steps)]


def _lifespan(rng: random.Random, now: datetime, status: str) -> tuple[datetime, datetime]:
    """First and last sighting, consistent with the status.

    A "gone" property has to have been unseen for longer than the scanner's
    grace period, or its own status could not have been reached.
    """
    if status == "gone":
        age = rng.randint(45, 240)
        first_seen = now - timedelta(days=age, hours=rng.randrange(24))
        return first_seen, first_seen + timedelta(days=rng.randint(10, age - 20))
    first_seen = now - timedelta(days=rng.randint(1, 180), hours=rng.randrange(24))
    return first_seen, now - timedelta(hours=rng.randrange(20))


def _jitter(rng: random.Random, degrees: float) -> float:
    """A pin scattered around its district centre, roughly half a kilometre."""
    return round(degrees + rng.uniform(-0.006, 0.006), 6)


def _placeholder_image(index: int) -> str:
    """A photo-shaped SVG carried inside the row, as a data URI.

    Deliberately not a URL. The corpus has to render with no network at all, and
    a link to a placeholder service would be both a request to somebody else's
    server and a way for a browser test to fail on their downtime.
    """
    hue = (index * 37) % 360
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480">'
        f'<rect width="640" height="480" fill="hsl({hue},38%,82%)"/>'
        f'<rect y="300" width="640" height="180" fill="hsl({hue},28%,70%)"/>'
        f'<rect x="180" y="150" width="280" height="230" fill="hsl({hue},34%,90%)"/>'
        f'<path d="M150 155 L320 62 L490 155 Z" fill="hsl({hue},30%,60%)"/>'
        f'<rect x="230" y="215" width="70" height="70" fill="hsl({hue},42%,66%)"/>'
        f'<rect x="345" y="215" width="70" height="70" fill="hsl({hue},42%,66%)"/>'
        f'<rect x="290" y="300" width="70" height="80" fill="hsl({hue},34%,56%)"/>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
