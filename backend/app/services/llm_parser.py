"""Optional LLM backend for the natural-language search assistant.

The hand-written parser in `query_parser.py` is deterministic, offline and the
default — this module is the opt-in alternative for phrasings its regex chain
cannot reach. It calls an OpenAI-compatible chat endpoint (so a local Ollama
server, a free cloud tier, or a paid API are one code path) and turns the reply
into the **same** `{"searches": [...]}` structure `parse_query` produces, reusing
`query_parser.build_search_entry` so the two backends cannot drift.

Fail-safe by construction: `parse_with_llm` returns `None` on anything that goes
wrong (no config, unreachable server, malformed JSON, empty result), and the
dispatcher (`query_parser.parse_query_auto`) then falls back to the deterministic
parser. The HTTP call is isolated in `_chat_completion` so tests exercise the
whole prompt/validate/convert path with a mocked client and never hit a network
(the same "no network in tests" rule as invariant 17).
"""

import json
import logging
import urllib.request

from .query_parser import PARAM_KEYS, build_search_entry

logger = logging.getLogger(__name__)

# Kept deliberately tight: the model's only job is extraction into a fixed shape,
# and a smaller instruction leaves less room for a 3B local model to improvise.
_SYSTEM_PROMPT = """You extract structured real-estate search parameters from a \
free-text query (Italian or English). Reply with ONLY a JSON object, no prose.

Shape:
{"searches": [ {
  "city": string,            // portal spelling, e.g. "Milano" not "Milan"; "" if unknown
  "province": string,        // "" unless the query names one distinct from the city
  "zone": string,            // neighbourhood/quarter, or ""
  "contract": "sale"|"rent", // "rent" for affitto/rental/al mese, else "sale"
  "min_price": number|null,  // euros; for rent it is euros/month
  "max_price": number|null,
  "min_rooms": number|null,  // Italian "locali": a 2-bedroom flat is 3 locali
  "max_rooms": number|null,
  "min_sqm": number|null
} ] }

Rules:
- One entry per alternative ("bilocale a Milano o trilocale a Torino" -> two entries).
- A lone budget figure is a maximum ("casa a 300k" -> max_price 300000).
- Use null, never 0, for an unspecified number. Use "", never null, for strings.
- Never invent a city that is not implied by the query."""


def _chat_completion(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
    """POST one chat completion and return the assistant message text.

    Isolated so tests can monkeypatch it: everything above and below is pure.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        # OpenAI + Ollama honour this; a server that ignores it just returns
        # text we still try to parse (and fall back from if it is not JSON).
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    """Parse the model's reply into a dict, tolerating a stray code fence.

    A model told to answer JSON usually does, but a local 3B one may wrap it in
    ```json fences or add a sentence — so if a direct parse fails, fall back to
    the first {...} span rather than giving up on an otherwise-good answer.
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _coerce_number(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _clean_params(raw: dict) -> dict:
    """Validate + coerce one model-produced params object into the builder's shape."""
    params: dict = {k: None for k in PARAM_KEYS}
    for key in ("city", "province", "zone"):
        val = raw.get(key)
        params[key] = val.strip() if isinstance(val, str) else ""
    contract = raw.get("contract")
    params["contract"] = "rent" if contract == "rent" else "sale"
    for key in ("min_price", "max_price", "min_rooms", "max_rooms", "min_sqm"):
        params[key] = _coerce_number(raw.get(key))
    return params


def parse_with_llm(query: str) -> dict | None:
    """Return the same shape as query_parser.parse_query, or None to fall back."""
    from ..config import load_settings

    settings = load_settings()
    base_url = (settings.get("llm_base_url") or "").strip()
    model = (settings.get("llm_model") or "").strip()
    api_key = (settings.get("llm_api_key") or "").strip()
    if not base_url or not model or not (query or "").strip():
        return None
    try:
        reply = _chat_completion(base_url, api_key, model, _SYSTEM_PROMPT, query)
        data = _extract_json(reply)
    except Exception as e:
        logger.warning("LLM parser: request/parse failed, falling back (%s)", e)
        return None

    raw_searches = data.get("searches") if isinstance(data, dict) else None
    if isinstance(data, dict) and raw_searches is None and data.get("city") is not None:
        raw_searches = [data]  # the model answered a single object, not a list
    if not isinstance(raw_searches, list) or not raw_searches:
        logger.warning("LLM parser: no usable searches in reply, falling back")
        return None

    searches = []
    contract_hint = _mentions_contract(query)
    for raw in raw_searches:
        if not isinstance(raw, dict):
            continue
        params = _clean_params(raw)
        searches.append(
            build_search_entry(
                params,
                # if the user never said sale/rent, flag the "sale" default out loud,
                # exactly as the deterministic parser does
                contract_assumed=(params["contract"] == "sale" and not contract_hint),
            )
        )
    if not searches:
        return None
    return {"searches": searches}


def _mentions_contract(query: str) -> bool:
    from .query_parser import _normalize, _parse_contract

    _, explicit = _parse_contract(_normalize(query))
    return explicit
