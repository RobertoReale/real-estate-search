"""Finding the boundary of one listing card in a results page, and lifting its
JSON-LD blocks out.

**Never CSS classes** (invariant 2): a card is "the last ancestor that still
contains links to only one ad", which is a property the portal cannot change
without breaking its own grid. A fixed number of levels, or a class name, both
broke on the first redesign — and the failure is silent, because climbing one
level too far reads the page footer's numbers as a price and a surface.
"""

import json
import re

# How many DOM levels the card-boundary climb may ascend before giving up.
# Measured card depths on both portals sit at 3-5 levels; the margin absorbs a
# few wrapper divs from a redesign. Shared with the email extractor's
# identical climb so the two cannot drift apart.
MAX_CARD_CLIMB = 8


def find_card_container(anchor, ad_path_re: re.Pattern):
    """Climbs from the ad link up to its card container.

    The card boundary is defined without relying on CSS classes: we climb up until
    the ancestor contains links to **only one** ad. The first ancestor containing two
    belongs to the results grid, so we stop right before it.

    This prevents climbing up into the page footer (where random numbers would be
    read as prices and square footage) when a card does not expose a price.

    `ad_path_re` must also match relative hrefs ("/annunci/123/"):
    this is how portals link ads within results pages.
    """

    def ad_ids(node) -> set[str]:
        ids = set()
        for a in node.find_all("a", href=True):
            m = ad_path_re.search(a["href"])
            if m:
                ids.add(m.group(1))
        return ids

    container = node = anchor
    for _ in range(MAX_CARD_CLIMB):
        parent = node.parent
        if parent is None or len(ad_ids(parent)) > 1:
            break
        container = node = parent
    return container


def extract_json_ld_blocks(html: str) -> list[dict]:
    """Extracts all <script type="application/ld+json"> blocks as dicts."""
    blocks = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks
