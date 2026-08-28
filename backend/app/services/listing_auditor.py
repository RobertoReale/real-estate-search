"""Optional LLM reading of a listing's own text, on demand.

An agency description is written to sell, and the facts that decide whether a
viewing is worth the trip are buried in its prose: a sitting tenant, building
fees the asking price does not include, a "da ristrutturare" three paragraphs
down, the sentence that becomes the first argument in a negotiation. No portal
filter reaches any of it, and neither does the grid — it is free text.

Three rules shape the whole module, and each has a reason:

* **Off by default, and never automatic.** `listing_audit_enabled` plus a
  configured endpoint is the opt-in, and only a user pressing the button on a
  card spends a request. No scan, no grid render and no batch calls this — the
  same stance every optional path here takes (invariant 18's shape, one level
  up), for the same reason: work the user did not ask for must not happen
  behind their back.
* **A model that invents a defect is worse than no auditor at all.** The prompt
  says to report only what the text states, "unknown" and the empty list are
  named as the correct answers, and every field of the reply is validated and
  bounded (`_clean_audit`) before it reaches the database. What comes out is a
  re-reading of the ad, never an appraisal — which is what the card prints
  beside it.
* **One model to configure, not two.** The HTTP call is
  `llm_parser.chat_completion`, the same OpenAI-compatible endpoint the search
  assistant uses (`llm_base_url` / `llm_api_key` / `llm_model`), so a local
  Ollama server set up once serves both.

Answers are remembered in `PropertyAudit`, keyed by a digest of the exact text
that was sent: re-opening a card is free, and an ad that has been rewritten or
re-priced is re-read instead of being answered from a row about text that no
longer exists. The same memory trick as GeocodeCache and CommuteCache, for the
same reason — the expensive half is the answer, and the input rarely moves.
"""

import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Property, PropertyAudit, utcnow
from .llm_parser import chat_completion, extract_json

logger = logging.getLogger(__name__)

# The vocabularies the reply is forced into. Anything else the model answers
# becomes "unknown": a value no screen can render is worse than an admission.
CONDITIONS = ("new", "renovated", "good", "to_renovate", "unknown")
TENANT_STATES = ("yes", "no", "unknown")

# Bounds on what may be stored and shown. A local model asked for a list can
# answer with an essay, and the card has to render whatever comes back.
MAX_TEXT_CHARS = 6000
MAX_SUMMARY_CHARS = 400
MAX_ITEMS = 6
MAX_ITEM_CHARS = 200

_SYSTEM_PROMPT = """You read ONE Italian real-estate listing and report only what \
its text actually says. Reply with ONLY a JSON object, no prose.

Shape:
{
  "summary": string,        // one sentence a buyer should read first; "" if the text says nothing useful
  "condition": "new"|"renovated"|"good"|"to_renovate"|"unknown",
  "tenant": "yes"|"no"|"unknown",  // "yes" only if it is sold with a tenant in place ("locato", "a reddito", "cedolare secca")
  "costs": [string],        // costs the asking price does not include, as stated ("spese condominiali", "riscaldamento centralizzato", works already approved)
  "concerns": [string],     // weak points to check ("piano terra", no lift, "asta", "nuda proprieta'", works needed)
  "negotiation": [string]   // facts in the text usable when making an offer
}

Rules:
- Report ONLY what the text states. Never guess, never infer from the price, never add general advice.
- An empty list is the correct answer when the text says nothing about that aspect.
- "unknown" is the correct answer when the text does not say.
- Write every string in English, at most 20 words, keeping the Italian term in brackets where it matters.
- Never make the same point in two fields."""


class ListingAuditError(Exception):
    """The audit could not be produced (feature off, nothing to read, no answer).

    Raised rather than swallowed because this path is only ever reached by a
    user pressing a button and waiting for it: telling them the model did not
    answer is the fail-open behaviour here. Nothing else in the application
    depends on it — a failed audit leaves the property exactly as it was.
    """


def is_configured(settings: dict) -> bool:
    """Whether pressing the button could produce anything at all."""
    return bool(
        settings.get("listing_audit_enabled")
        and (settings.get("llm_base_url") or "").strip()
        and (settings.get("llm_model") or "").strip()
    )


def listing_text(prop: Property) -> str:
    """The exact text sent to the model: the ad's own words, plus the facts.

    The description is the **longest** of the merged ads', not the first: the
    same property is published by several agencies and one of them usually
    wrote more than "trilocale luminoso". The structured facts ride along
    because the prose is read against them — "spese incluse" means one thing at
    90 m² and another at 40 — and because a number the database already knows
    must never be left to the model to infer.
    """
    descriptions = [(listing.description or "").strip() for listing in prop.listings]
    description = max(descriptions, key=len, default="")
    if not description:
        return ""

    facts = [
        f"{prop.sqm:.0f} sqm" if prop.sqm else "",
        f"{prop.rooms} rooms" if prop.rooms else "",
        f"floor {prop.floor}" if prop.floor else "",
        f"{prop.current_min_price:.0f} EUR" if prop.current_min_price else "",
        "rental" if prop.contract == "rent" else "for sale",
    ]
    agencies = sorted({(listing.agency or "").strip() for listing in prop.listings} - {""})
    lines = [
        f"Title: {prop.title or '(none)'}",
        f"Location: {' · '.join(x for x in (prop.city, prop.zone, prop.address) if x) or '(none)'}",
        f"Facts: {', '.join(f for f in facts if f)}",
    ]
    if agencies:
        lines.append(f"Agency: {', '.join(agencies)}")
    lines.append("Description:")
    lines.append(description)
    return "\n".join(lines)[:MAX_TEXT_CHARS]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_line(value: object, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, str) else ""


def _clean_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [_clean_line(item, MAX_ITEM_CHARS) for item in value]
    return [item for item in items if item][:MAX_ITEMS]


def _clean_tenant(value: object) -> str:
    # Models answer this one as a boolean about as often as as a string, and a
    # dropped `true` would read on the card as "nothing said about a tenant" —
    # the one answer that must never be invented in either direction.
    if isinstance(value, bool):
        return "yes" if value else "no"
    state = _clean_line(value, 16).lower()
    return state if state in TENANT_STATES else "unknown"


def _clean_audit(raw: object) -> dict:
    """Validate and bound one model reply into the shape the card renders."""
    data = raw if isinstance(raw, dict) else {}
    condition = _clean_line(data.get("condition"), 16).lower()
    return {
        "summary": _clean_line(data.get("summary"), MAX_SUMMARY_CHARS),
        "condition": condition if condition in CONDITIONS else "unknown",
        "tenant": _clean_tenant(data.get("tenant")),
        "costs": _clean_list(data.get("costs")),
        "concerns": _clean_list(data.get("concerns")),
        "negotiation": _clean_list(data.get("negotiation")),
    }


def _row(db: Session, prop: Property) -> PropertyAudit | None:
    return db.scalar(select(PropertyAudit).where(PropertyAudit.property_id == prop.id))


def _as_dict(row: PropertyAudit, *, cached: bool, digest: str) -> dict | None:
    """One stored row as the API shape, or None if its payload is unreadable.

    Unreadable means a row written by an older shape (or a truncated write):
    treating it as absent re-asks the model, which is cheaper than teaching
    every reader to cope with a half-payload.
    """
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return {
        **_clean_audit(payload),
        "model": row.model,
        "created_at": row.created_at,
        "cached": cached,
        # The listing has been rewritten since this answer: still worth showing
        # (it is about the same property), but the card says so rather than
        # presenting it as a reading of the text now on screen.
        "stale": row.text_digest != digest,
    }


def stored_audit(db: Session, prop: Property) -> dict | None:
    """The audit already paid for, or None. Never touches the network — this is
    what a card opening may call, exactly like the commute annotation."""
    row = _row(db, prop)
    if row is None:
        return None
    return _as_dict(row, cached=True, digest=_digest(listing_text(prop)))


def audit_property(db: Session, prop: Property, *, force: bool = False) -> dict:
    """Read this property's listing text with the configured model.

    Answers from the stored row when it is about the same text and the same
    model — pressing the button twice costs one request, not two. `force`
    re-asks regardless, which is the way back from an answer the user does not
    trust (a smaller model on a long description) after changing the model.
    """
    from ..config import load_settings

    settings = load_settings()
    if not settings.get("listing_audit_enabled"):
        raise ListingAuditError("The listing auditor is off: turn it on in Settings")
    base_url = (settings.get("llm_base_url") or "").strip()
    model = (settings.get("llm_model") or "").strip()
    api_key = (settings.get("llm_api_key") or "").strip()
    if not base_url or not model:
        raise ListingAuditError(
            "No language model is configured: set its base URL and model name in Settings"
        )

    text = listing_text(prop)
    if not text:
        raise ListingAuditError("This listing has no description to read")
    digest = _digest(text)

    row = _row(db, prop)
    if row is not None and not force and row.text_digest == digest and row.model == model:
        stored = _as_dict(row, cached=True, digest=digest)
        if stored is not None:
            return stored

    try:
        reply = chat_completion(base_url, api_key, model, _SYSTEM_PROMPT, text)
        data = extract_json(reply)
    except Exception as e:
        logger.warning("listing auditor: request/parse failed for property #%s (%s)", prop.id, e)
        raise ListingAuditError(f"The model did not answer: {e}") from e

    audit = _clean_audit(data)
    if row is None:
        row = PropertyAudit(property_id=prop.id)
        db.add(row)
    row.text_digest = digest
    row.model = model
    row.payload = json.dumps(audit, ensure_ascii=False)
    row.created_at = utcnow()
    db.commit()
    return {**audit, "model": model, "created_at": row.created_at, "cached": False, "stale": False}
