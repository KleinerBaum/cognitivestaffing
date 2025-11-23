"""Tests for profile normalization helpers."""

from typing import Mapping

import pytest

from core.normalization import normalize_url
from core.schema import canonicalize_profile_payload
from models.need_analysis import NeedAnalysisProfile
from utils.normalization import NormalizedProfilePayload
from utils.normalization.profile_normalization import (
    normalize_company_size,
    normalize_profile,
)


def test_normalize_company_size_parses_numbers() -> None:
    assert normalize_company_size("rund 3.370 Menschen") == "3370"
    assert normalize_company_size("mehr als 500 Mitarbeiter") == "500+"
    assert normalize_company_size("501 – 1000 Mitarbeitende") == "501-1000"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("https://example.com", "https://example.com"),
        (" http://foo.bar/path ", "http://foo.bar/path"),
        ("", None),
        (None, None),
        ("notaurl", None),
    ],
)
def test_normalize_url_pattern_guard(value: str | None, expected: str | None) -> None:
    assert normalize_url(value) == expected


def test_canonicalize_profile_payload_classifies_mixed_skills() -> None:
    payload = canonicalize_profile_payload(
        {
            "skills": {
                "must_have": [
                    "Python",
                    "Clear communication",
                    "German B2",
                ],
                "nice_to_have": [
                    "AWS Certified Solutions Architect",
                    "Tableau",
                ],
            }
        }
    )

    requirements = payload.get("requirements", {})
    assert requirements["hard_skills_required"] == ["Python"]
    assert requirements["soft_skills_required"] == ["Clear communication"]
    assert requirements["languages_required"] == ["German B2"]
    assert requirements["tools_and_technologies"] == ["Tableau"]
    assert requirements["certifications"] == ["AWS Certified Solutions Architect"]


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

    normalized_payload: NormalizedProfilePayload = normalize_profile(profile)
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

    normalized: NormalizedProfilePayload = normalize_profile(invalid_payload)

    assert normalized["company"]["name"] == "Acme"
    assert calls, "Expected JSON repair fallback to be invoked"


def test_normalize_profile_returns_model_dump_on_failed_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = NeedAnalysisProfile()
    original_dump: NormalizedProfilePayload = profile.model_dump()

    def broken_normalizer(_: Mapping[str, object]) -> Mapping[str, object]:
        return {"company": "Acme"}

    monkeypatch.setattr(
        "utils.normalization.profile_normalization._normalize_profile_mapping",
        broken_normalizer,
    )
    monkeypatch.setattr(
        "utils.normalization.profile_normalization._attempt_llm_repair",
        lambda *_args, **_kwargs: None,
        raising=False,
    )

    normalized: NormalizedProfilePayload = normalize_profile(profile)

    assert normalized == original_dump


def test_normalize_profile_handles_repair_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising_repair(payload: Mapping[str, object], *, errors: object | None = None) -> Mapping[str, object]:
        raise ValueError("invalid json")

    monkeypatch.setattr(
        "llm.json_repair.repair_profile_payload",
        raising_repair,
        raising=False,
    )

    invalid_payload = {"company": "Acme"}

    normalized: NormalizedProfilePayload = normalize_profile(invalid_payload)

    assert normalized == NeedAnalysisProfile().model_dump()


def test_normalize_profile_converts_interview_stage_lists() -> None:
    payload = NeedAnalysisProfile().model_dump()
    payload["process"] = {"interview_stages": ["3", "phone screen"]}

    normalized_payload: NormalizedProfilePayload = normalize_profile(payload)
    normalized = NeedAnalysisProfile.model_validate(normalized_payload)

    assert normalized.process.interview_stages == 3


def test_normalize_profile_handles_empty_interview_stage_list() -> None:
    payload = NeedAnalysisProfile().model_dump()
    payload["process"] = {"interview_stages": []}

    normalized_payload: NormalizedProfilePayload = normalize_profile(payload)
    normalized = NeedAnalysisProfile.model_validate(normalized_payload)

    assert normalized.process.interview_stages is None


def test_normalize_profile_pipeline_applies_aliases() -> None:
    """Alias keys should survive canonicalisation plus normalization."""

    raw_payload = {
        "company": {"tagline": "Simplify hiring"},
        "role": {
            "department": "Operations",
            "team_structure": "Core Platform",
            "reporting_line": "CTO",
        },
    }

    canonical = canonicalize_profile_payload(raw_payload)
    normalized_payload: NormalizedProfilePayload = normalize_profile(canonical)
    normalized = NeedAnalysisProfile.model_validate(normalized_payload)

    assert normalized.company.claim == "Simplify hiring"
    assert normalized.department.name == "Operations"
    assert normalized.team.name == "Core Platform"
    assert normalized.team.reporting_line == "CTO"


def test_normalize_profile_enriches_skill_mappings() -> None:
    payload = {
        "requirements": {
            "hard_skills_required": ["Excel"],
            "soft_skills_optional": ["teamwork"],
        }
    }

    normalized = normalize_profile(payload)

    skill_mappings = normalized["requirements"]["skill_mappings"]
    hard_skill = skill_mappings["hard_skills_required"][0]
    assert hard_skill["normalized_name"] == "Microsoft Excel"
    assert hard_skill["esco_uri"]

    soft_skill = skill_mappings["soft_skills_optional"][0]
    assert soft_skill["normalized_name"] == "Teamwork"


