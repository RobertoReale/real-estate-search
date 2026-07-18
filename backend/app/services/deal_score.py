"""Deal Score: a congruity & expected-discount reading for each property.

Portals show only the asking price. This turns the data the app already holds
into an estimate of how that asking sits against fair value, expressed as a
score roughly in [-50, +50] where **positive = priced below the local market**
(a potential deal) and negative = above it. It combines three signals, each of
which the app computes elsewhere:

1. **Micro-zone €/sqm** — how far the listing sits from its zone (or city)
   median, the same `sqm_price_delta_pct` the market-position badge shows. A
   listing 16% below the median contributes +16.
2. **Condition cues** — free-text signals from the listing that explain *why* a
   price is low or high: "da ristrutturare" means the discount is earned, not a
   bargain (−15); "ristrutturato"/"classe A" justifies a premium (+10). Matched
   on word boundaries via the filter engine, so "asta" ⊄ "vasta".
3. **Agency signature** — the agency's own historical median discount
   (`market_velocity`), used only to estimate a realistic **proposal range**,
   not to move the score itself: what an agency *might* concede is negotiation
   headroom, not evidence the current price is off.

Like the market-position and match annotations it is transient (never persisted)
and needs the market position computed first (it reads `sqm_price_delta_pct`).
With no median available the score is None — the badge simply does not appear.
"""

from datetime import UTC

from ..models import Property
from .filter_engine import find_excluded_keyword

# Italian, verbatim like DEFAULT_EXCLUDED_KEYWORDS: they must match the portals'
# own wording. "Needs work" cues justify a low price (the discount is not a
# deal); "renovated / high class" cues justify a premium.
CONDITION_NEGATIVE = [
    "da ristrutturare",
    "da ristrutturare completamente",
    "necessita di ristrutturazione",
    "da rimodernare",
    "da ammodernare",
    "al grezzo",
]
CONDITION_POSITIVE = [
    "ristrutturato",
    "ristrutturata",
    "finemente ristrutturato",
    "completamente ristrutturato",
    "nuova costruzione",
    "di recente costruzione",
    "classe a",
    "classe energetica a",
]
NEGATIVE_MODIFIER = -15
POSITIVE_MODIFIER = 10

# Thresholds for the human-readable label. Kept wider than the market badge's
# ±5%, because the Deal Score folds in condition adjustments and a bit of noise.
UNDERVALUED_AT = 10
OVERPRICED_AT = -10


def _condition_adjustment(prop: Property) -> tuple[int, list[str]]:
    texts = [prop.title, *(l.description for l in prop.listings)]
    adj = 0
    reasons: list[str] = []
    if find_excluded_keyword(texts, CONDITION_NEGATIVE):
        adj += NEGATIVE_MODIFIER
        reasons.append(f"needs renovation ({NEGATIVE_MODIFIER}%)")
    if find_excluded_keyword(texts, CONDITION_POSITIVE):
        adj += POSITIVE_MODIFIER
        reasons.append(f"renovated / high energy class (+{POSITIVE_MODIFIER}%)")
    return adj, reasons


def _agency_signature(prop: Property, signatures: dict[str, dict]) -> dict | None:
    """The richest agency signature among this property's listings, if any.

    Lookup is casefolded to match how market_velocity keys its samples, so a
    portal-to-portal casing difference cannot lose the signature."""
    best: dict | None = None
    for listing in prop.listings:
        sig = signatures.get((listing.agency or "").strip().casefold())
        if sig and (best is None or sig["sample"] > best["sample"]):
            best = sig
    return best


def _round_k(value: float) -> int:
    """Round to the nearest €1,000 — a proposal figure to the euro reads as
    false precision."""
    return int(round(value / 1000.0) * 1000)


def _target_range(prop: Property, expected_discount: float | None) -> tuple[int | None, int | None]:
    """A suggested offer band, only for sales priced above an estimable value.

    The estimate is the lower of the fair value implied by the area median and
    the price the agency's own discounting behaviour suggests it will accept.
    Returns (low, high) rounded to €1,000, or (None, None) when there is no room
    below the asking price to suggest."""
    if prop.contract != "sale" or not prop.current_min_price:
        return None, None
    asking = prop.current_min_price
    estimate: float | None = None
    if prop.area_median_sqm_price and prop.sqm:
        fair = prop.area_median_sqm_price * prop.sqm
        if fair < asking:
            estimate = fair
    if expected_discount:
        discounted = asking * (1 - expected_discount / 100.0)
        estimate = min(estimate, discounted) if estimate is not None else discounted
    if estimate is None or estimate >= asking:
        return None, None
    return _round_k(estimate * 0.97), _round_k(estimate)


def _score_property(prop: Property, signatures: dict[str, dict]) -> None:
    reasons: list[str] = []
    base: float | None = None
    if prop.sqm_price_delta_pct is not None:
        base = -prop.sqm_price_delta_pct
        scope = prop.area_median_scope or "area"
        if prop.sqm_price_delta_pct <= -1:
            reasons.append(f"{abs(prop.sqm_price_delta_pct):.0f}% below {scope} median")
        elif prop.sqm_price_delta_pct >= 1:
            reasons.append(f"{prop.sqm_price_delta_pct:.0f}% above {scope} median")

    cond_adj, cond_reasons = _condition_adjustment(prop)
    reasons += cond_reasons

    sig = _agency_signature(prop, signatures)
    expected_discount = sig["median_drop_pct"] if sig else None
    if expected_discount:
        reasons.append(f"agency typically cuts {expected_discount:.0f}%")

    prop.expected_discount_pct = round(expected_discount, 1) if expected_discount else None
    if base is None:
        # Without a local median there is no fair-value anchor: no score, and
        # the agency headroom alone is not enough to suggest a target.
        prop.deal_score = None
        prop.deal_label = None
        prop.deal_reasons = []
        prop.target_price_low = None
        prop.target_price_high = None
        return

    score = round(max(-50.0, min(50.0, base + cond_adj)))
    prop.deal_score = score
    prop.deal_label = (
        "undervalued"
        if score >= UNDERVALUED_AT
        else "overpriced"
        if score <= OVERPRICED_AT
        else "fair"
    )
    prop.deal_reasons = reasons
    low, high = _target_range(prop, expected_discount)
    prop.target_price_low = low
    prop.target_price_high = high


def _agency_signatures(db) -> dict[str, dict]:
    """agency name -> its market_velocity behaviour row (median discount etc.).

    Built over the whole tracked set (not just the page being scored) so the
    per-agency medians rest on all the evidence, and gated by the same
    MIN_SAMPLE rule market_velocity applies."""
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from .market_velocity import compute_agency_behavior

    props = list(
        db.scalars(
            select(Property)
            .options(selectinload(Property.listings))
            .where(Property.status.in_(("active", "filtered", "gone")))
        )
    )
    rows = compute_agency_behavior(db, props, datetime.now(UTC))
    return {r["agency"].casefold(): r for r in rows}


def annotate_deal_scores(db, props: list[Property]) -> None:
    """Attaches the transient deal fields read by PropertyOut and the notifier.

    Requires `annotate_market_position` to have run first (it reads
    `sqm_price_delta_pct`/`area_median_*`). Computes the agency signatures once
    for the whole batch."""
    if not props:
        return
    signatures = _agency_signatures(db)
    for p in props:
        _score_property(p, signatures)
