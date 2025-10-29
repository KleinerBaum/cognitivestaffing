"""Tests for the normalisation utilities."""

import json
from typing import Mapping
from types import SimpleNamespace

import pytest

from models.need_analysis import NeedAnalysisProfile
from utils.normalization import (
    normalize_city_name,
    normalize_company_size,
    normalize_country,
    normalize_language,
    normalize_language_list,
    normalize_phone_number,
    normalize_profile,
    normalize_website_url,
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


def test_normalize_city_name_uses_llm_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from utils import normalization

    calls: list[list[dict[str, str]]] = []

    monkeypatch.setattr(normalization, "USE_RESPONSES_API", True, raising=False)
    monkeypatch.setattr(normalization, "is_llm_enabled", lambda: True)
    monkeypatch.setattr(normalization, "get_model_for", lambda *_, **__: "gpt-test")

    def fake_call_responses(messages, **kwargs):
        calls.append(messages)
        return SimpleNamespace(
            content=json.dumps({"city": "Hamburg"}),
            usage={},
            response_id=None,
            raw_response={},
        )

    monkeypatch.setattr(normalization, "call_responses", fake_call_responses)

    result = normalization.normalize_city_name(" remote möglich")

    assert result == "Hamburg"
    assert calls and calls[0][0]["role"] == "system"


def test_normalize_company_size_parses_numbers() -> None:
    assert normalize_company_size("rund 3.370 Menschen") == "3370"
    assert normalize_company_size("mehr als 500 Mitarbeiter") == "500+"
    assert normalize_company_size("501 – 1000 Mitarbeitende") == "501-1000"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" +49 (0)30-123 4567 ext. 89 ", "+49 30 1234567 ext 89"),
        ("030/1234567", "030 1234567"),
        ("tel.: 123", "123"),
        ("call me maybe", None),
        (None, None),
    ],
)
def test_normalize_phone_number_variants(raw: str | None, expected: str | None) -> None:
    assert normalize_phone_number(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" example.com/jobs ", "https://example.com/jobs"),
        ("HTTP://Sub.Example.com/jobs/", "http://sub.example.com/jobs"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_website_url_variants(raw: str | None, expected: str | None) -> None:
    assert normalize_website_url(raw) == expected


def test_normalize_profile_applies_string_rules() -> None:
    profile = NeedAnalysisProfile.model_validate(
        {
            "company": {
                "logo_url": " https://example.com/logo.svg ",
                "brand_color": "99cc00",
            },
            "position": {"job_title": "Lead Developer (m/w/d)"},
            "location": {"primary_city": "in Düsseldorf eine"},
            "requirements": {"hard_skills_required": [" Python ", "python", ""]},
            "responsibilities": {"items": ["Build APIs ", "Build APIs"]},
        }
    )

    normalized_payload = normalize_profile(profile)
    normalized = NeedAnalysisProfile.model_validate(normalized_payload)

    assert normalized.position.job_title == "Lead Developer"
    assert normalized.location.primary_city == "Düsseldorf"
    assert str(normalized.company.logo_url) == "https://example.com/logo.svg"
    assert normalized.company.brand_color == "#99CC00"
    assert normalized.requirements.hard_skills_required == ["Python"]
    assert normalized.responsibilities.items == ["Build APIs"]


def test_normalize_profile_uses_json_repair_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Mapping[str, object]] = []

    def fake_repair(payload: Mapping[str, object], *, errors: object | None = None) -> Mapping[str, object] | None:
        calls.append(payload)
        return {"company": {"name": "Acme"}}

    monkeypatch.setattr("llm.json_repair.repair_profile_payload", fake_repair, raising=False)

    invalid_payload = {"company": "Acme"}

    normalized = normalize_profile(invalid_payload)

    assert normalized["company"]["name"] == "Acme"
    assert calls, "Expected JSON repair fallback to be invoked"
