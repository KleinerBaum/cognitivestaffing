"""Tests for geographic normalization helpers."""

import json
from types import SimpleNamespace

import pytest

import config
from utils.normalization import geo_normalization
from utils.normalization.geo_normalization import (
    normalize_city_name,
    normalize_country,
    normalize_language,
    normalize_language_list,
)


def test_normalize_country_handles_german_inputs() -> None:
    assert normalize_country("Deutschland") == "Germany"
    assert normalize_country("DE") == "Germany"


def test_normalize_language_handles_german_variants() -> None:
    assert normalize_language("Deutsch") == "German"
    assert normalize_language("de") == "German"
    assert normalize_language_list(["Deutsch", "english", "GERMAN"]) == [
        "German",
        "English",
    ]


def test_normalize_city_name_strips_prefix_and_suffix() -> None:
    assert normalize_city_name("in Düsseldorf eine") == "Düsseldorf"
    assert normalize_city_name("bei Berlin, remote möglich") == "Berlin"


@pytest.mark.parametrize("value", [None, " ", "unknown"])
def test_normalize_city_name_handles_empty_inputs(value: str | None) -> None:
    assert normalize_city_name(value) in {"", value.title() if value and value.strip() else ""}


def test_normalize_city_name_uses_llm_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[dict[str, str]]] = []

    previous_mode = config.USE_RESPONSES_API
    config.set_api_mode(True)
    monkeypatch.setattr(geo_normalization, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(geo_normalization, "get_model_for", lambda *_, **__: "gpt-test")

    def fake_call_responses(messages, **kwargs):
        calls.append(messages)
        return SimpleNamespace(
            content=json.dumps({"city": "Hamburg"}),
            usage={},
            response_id=None,
            raw_response={},
            used_chat_fallback=False,
        )

    monkeypatch.setattr(geo_normalization, "call_responses_safe", fake_call_responses)

    try:
        result = geo_normalization.normalize_city_name(" remote möglich")

        assert result == "Hamburg"
        assert calls and calls[0][0]["role"] == "system"
    finally:
        config.set_api_mode(previous_mode)
