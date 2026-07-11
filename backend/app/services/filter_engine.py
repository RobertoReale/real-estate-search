"""Keyword filter: excludes ads whose text contains forbidden words
(e.g., "nuda proprietà", "piano terra").

Comparison is case-insensitive, accent-insensitive, and bound to word
boundaries: without the latter constraint, "asta" (auction) would discard
properties located in the "Castanese" zone or described as having "vasta metratura".
"""
import re
import unicodedata
from collections.abc import Sequence
from functools import lru_cache


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


@lru_cache(maxsize=256)
def _pattern(keyword: str) -> re.Pattern | None:
    words = _normalize(keyword).split()
    if not words:
        return None
    # "piano terra" must tolerate multiple whitespaces between words
    body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(rf"(?<!\w){body}(?!\w)")


def find_excluded_keyword(
    texts: Sequence[str | None], excluded_keywords: list[str]
) -> str | None:
    """Returns the first forbidden keyword found in the texts, or None if clean."""
    haystack = _normalize(" ".join(t for t in texts if t))
    if not haystack:
        return None
    for kw in excluded_keywords:
        pattern = _pattern(kw)
        if pattern and pattern.search(haystack):
            return kw
    return None


def parse_keywords_csv(csv: str) -> list[str]:
    return [k.strip() for k in (csv or "").split(",") if k.strip()]
