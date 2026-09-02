"""Reading a portal page's own words: is this ad gone, did this search match
nothing, is this a DataDome wall?

**The gone/empty markers are matched against VISIBLE text only** (invariant 16).
Every Immobiliare ad page — live OR removed — embeds the portal's i18n error
dictionary, "non è più disponibile" included, inside its Next.js JSON, so a bare
substring scan over the raw HTML reported *every live ad as gone*. The block
markers are the deliberate exception: they run against the raw HTML because one
signal is a `<script>` src.

The markers stay in Italian for the same reason `DEFAULT_EXCLUDED_KEYWORDS` does
— they must match the portals' pages verbatim.
"""

import re

# What the portals write when the ad is gone. Kept in Italian for the same
# reason as DEFAULT_EXCLUDED_KEYWORDS: it must match their pages verbatim.
AD_GONE_MARKERS = (
    "non è presente sul nostro sito",  # Immobiliare's 404 page
    "non è più disponibile",  # both portals
    "annuncio non disponibile",
    "immobile non disponibile",
)

# What the portals write on a search whose filters matched nothing. Idealista
# serves this page with HTTP 404 — the very status a dead slug gets — so the
# status code alone cannot tell "no flats here today" from "no such zone": only
# the page can. Measured live on both portals; Immobiliare answers 200 instead,
# so it reaches us as an empty parse rather than an exception.
SEARCH_EMPTY_MARKERS = (
    "non abbiamo trovato quello che stavi cercando",  # Idealista
    "non ci sono annunci che corrispondano ai tuoi criteri",
    "non ci sono annunci per la tua ricerca",  # Immobiliare
)

# DataDome's interstitial "block" wall (the "Access is temporarily restricted"
# page). Not necessarily a solvable CAPTCHA widget — often just static text —
# but always a block, never the ad. Confirmed ABSENT from live ad pages, so it
# safely complements the 403/429 + "captcha" heuristic for a wall that arrives
# as HTTP 200 with the word "captcha" nowhere in its markup. Matched against the
# RAW HTML because one signal (`geo.captcha-delivery.com`) is a <script> src.
DATADOME_BLOCK_MARKERS = (
    "access is temporarily restricted",
    "we detected unusual activity",
    "geo.captcha-delivery.com",
    "please enable js and disable any ad blocker",
)

# How a search page states the size of its own result set: "1.234 case in
# vendita a Milano". Both portals head their results with that sentence, and it
# is the only page-count evidence the HTML paths get — neither publishes a
# number of pages anywhere a parser can reach. Italian, and matched on visible
# text, for the same reasons as the markers above; the noun is required so a
# card's "3 locali" or a footer's "case in vendita a Roma" cannot be read as a
# total.
SEARCH_TOTAL_RE = re.compile(
    r"(\d[\d.]*)\s+(?:case|annunci|immobili|appartamenti)\s+in\s+(?:vendita|affitto)"
)


def _visible_text(html: str) -> str:
    """Lowercased text a human would actually see, with <script>/<style>/
    <template>/<noscript> stripped out.

    This matters because every Immobiliare ad page — live OR removed — embeds
    the portal's i18n error dictionary (including "non è più disponibile")
    inside its Next.js JSON. Matching the gone markers against the raw HTML+JS
    therefore reports *live* ads as gone; the rendered text carries the message
    only when the page truly is the gone page. Returns "" when the HTML can't be
    parsed: without proof we must not claim "gone" (invariant 16)."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "template", "noscript"]):
            tag.decompose()
        # Runs of whitespace collapse to one space: a reader does not see the
        # line break a portal happens to put inside a sentence, so a marker
        # phrase must not depend on where the markup wraps.
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).lower()
    except Exception:
        return ""


def text_says_gone(html: str) -> bool:
    """True when the page's VISIBLE text carries a portal "ad gone" message."""
    text = _visible_text(html)
    return any(m in text for m in AD_GONE_MARKERS)


def text_says_no_results(html: str) -> bool:
    """True when the page's VISIBLE text is the portal's own "nothing matched"
    page — a real answer about an empty search, not a failure.

    Visible text only, for the same reason as text_says_gone: the portals ship
    their i18n dictionaries inside the page's JSON, so a raw substring scan would
    call every page empty. Getting that backwards is the dangerous direction —
    it would silence the "no listings extracted" alarm that catches a portal
    changing its markup.
    """
    text = _visible_text(html)
    return any(m in text for m in SEARCH_EMPTY_MARKERS)


def declared_result_total(html: str) -> int | None:
    """How many results the search page says it matched, or None if it does not.

    None is the answer that must be preserved: a scan reports "241 of about
    1,050" only where the portal itself published the 1,050, and reports "241,
    and there may be more" where it did not. Guessing the second number is the
    one way this feature can be worse than the silence it replaces.

    Visible text only, like every other reading in this module — the portals
    ship their i18n dictionaries inside the page JSON, so a raw scan would find
    the sentence on pages that never showed it.
    """
    match = SEARCH_TOTAL_RE.search(_visible_text(html))
    if not match:
        return None
    try:
        # Italian thousands separators: "1.234" is 1234, not 1.234
        return int(match.group(1).replace(".", ""))
    except ValueError:
        return None


def has_block_marker(html: str) -> bool:
    """True when the raw HTML carries DataDome's interstitial-wall signature."""
    if not html:
        return False
    low = html.lower()
    return any(m in low for m in DATADOME_BLOCK_MARKERS)
