"""Optional LLM backend for the natural-language search assistant.

Every test mocks the HTTP call (`_chat_completion`), so the whole
prompt/validate/convert path runs with no network — the deterministic default is
never disturbed and CI never talks to a model (invariant 17's spirit).
"""
from app import config
from app.services import llm_parser
from app.services.query_parser import parse_query_auto


def _enable_llm(monkeypatch, reply):
    monkeypatch.setattr(config, "load_settings", lambda: {
        **config.DEFAULT_SETTINGS,
        "nl_parser_backend": "llm",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_model": "qwen2.5",
    })
    captured = {}

    def fake(base_url, api_key, model, system, user):
        captured["base_url"] = base_url
        captured["model"] = model
        captured["system"] = system
        captured["user"] = user
        return reply

    monkeypatch.setattr(llm_parser, "_chat_completion", fake)
    return captured


def test_llm_reply_becomes_the_same_search_shape(monkeypatch):
    captured = _enable_llm(monkeypatch, '{"searches": [{"city": "Milano", '
                           '"contract": "rent", "max_price": 1200, "min_rooms": 3}]}')
    result = parse_query_auto("2-bedroom rental in Milan under 1200")
    assert captured["model"] == "qwen2.5"
    assert captured["user"] == "2-bedroom rental in Milan under 1200"
    assert len(result["searches"]) == 1
    p = result["searches"][0]["params"]
    assert p["city"] == "Milano"
    assert p["contract"] == "rent"
    assert p["max_price"] == 1200
    assert p["min_rooms"] == 3
    # every builder key is present even though the model omitted most of them
    assert p["zone"] == "" and p["min_sqm"] is None
    # and it still shows its work like the deterministic parser
    assert result["searches"][0]["interpretation"]


def test_multiple_alternatives_survive(monkeypatch):
    _enable_llm(monkeypatch,
                '{"searches": [{"city": "Milano", "contract": "sale"}, '
                '{"city": "Torino", "contract": "sale"}]}')
    result = parse_query_auto("bilocale a Milano o a Torino")
    cities = [s["params"]["city"] for s in result["searches"]]
    assert cities == ["Milano", "Torino"]


def test_a_single_object_reply_is_accepted(monkeypatch):
    _enable_llm(monkeypatch, '{"city": "Roma", "contract": "sale", "max_price": 300000}')
    result = parse_query_auto("casa a Roma 300k")
    assert result["searches"][0]["params"]["city"] == "Roma"


def test_fenced_json_is_tolerated(monkeypatch):
    _enable_llm(monkeypatch,
                'Sure!\n```json\n{"searches": [{"city": "Bologna", "contract": "rent"}]}\n```')
    result = parse_query_auto("affitto a Bologna")
    assert result["searches"][0]["params"]["city"] == "Bologna"


def test_missing_city_gets_the_same_warning_as_the_deterministic_parser(monkeypatch):
    _enable_llm(monkeypatch, '{"searches": [{"city": "", "contract": "sale"}]}')
    result = parse_query_auto("un trilocale luminoso")
    assert any("could not tell which city" in w
               for w in result["searches"][0]["warnings"])


def test_malformed_reply_falls_back_to_deterministic(monkeypatch):
    _enable_llm(monkeypatch, "this is not json at all")
    # The deterministic parser handles the query instead of raising.
    result = parse_query_auto("bilocale a Milano")
    assert result["searches"][0]["params"]["city"] == "Milano"


def test_request_error_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {
        **config.DEFAULT_SETTINGS,
        "nl_parser_backend": "llm",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_model": "qwen2.5",
    })

    def boom(*a, **k):
        raise ConnectionError("server down")

    monkeypatch.setattr(llm_parser, "_chat_completion", boom)
    result = parse_query_auto("casa a Roma")
    assert result["searches"][0]["params"]["city"] == "Roma"


def test_deterministic_is_the_default_and_never_calls_the_model(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: dict(config.DEFAULT_SETTINGS))

    def boom(*a, **k):
        raise AssertionError("the model must not be called on the default backend")

    monkeypatch.setattr(llm_parser, "_chat_completion", boom)
    result = parse_query_auto("bilocale a Milano")
    assert result["searches"][0]["params"]["city"] == "Milano"


def test_llm_backend_with_no_config_falls_back(monkeypatch):
    # Selected "llm" but never filled in a base URL/model: fail safe, not error.
    monkeypatch.setattr(config, "load_settings", lambda: {
        **config.DEFAULT_SETTINGS, "nl_parser_backend": "llm",
    })
    assert llm_parser.parse_with_llm("casa a Roma") is None
    result = parse_query_auto("casa a Roma")
    assert result["searches"][0]["params"]["city"] == "Roma"
