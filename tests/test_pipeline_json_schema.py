"""Ensure high-level pipelines pass JSON schema configuration to call_chat_api."""

from __future__ import annotations

import sys
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from jsonschema import Draft202012Validator, ValidationError

from generators import interview_guide as interview_mod
from generators import job_ad as job_ad_mod
from openai_utils.api import ChatCallResult
from pipelines import extraction as extraction_mod
from pipelines import followups as followups_mod
from pipelines import matching as matching_mod
from pipelines import profile_summary as profile_summary_mod
from schemas import (
    CANDIDATE_MATCHES_SCHEMA,
    FOLLOW_UPS_SCHEMA,
    INTERVIEW_GUIDE_SCHEMA,
    JOB_AD_SCHEMA,
    PROFILE_SUMMARY_SCHEMA,
    VACANCY_EXTRACTION_SCHEMA,
)


def _build_interview_guide_payload() -> dict[str, Any]:
    return {
        "metadata": {
            "language": "en",
            "heading": "Interview guide",
            "job_title": "Customer Success Manager",
            "audience": "Hiring Panel",
            "audience_label": "Panel",
            "tone": "Professional",
            "tone_label": "Professional",
            "culture_note": "Highlight collaboration.",
        },
        "questions": [
            {
                "question": "Tell me about a time you improved a client workflow.",
                "focus": "Process improvement",
                "evaluation": "Look for structured approach and ROI.",
            },
            {
                "question": "Describe how you manage conflicting priorities.",
                "focus": "Prioritization",
                "evaluation": "Seek proactive communication cues.",
            },
            {
                "question": "How do you mentor new team members?",
                "focus": "Coaching",
                "evaluation": "Expect concrete onboarding tactics.",
            },
        ],
        "focus_areas": [
            {
                "label": "Customer Impact",
                "items": [
                    "Understands churn risks",
                    "Shares win stories",
                ],
            }
        ],
        "evaluation_notes": [
            "Add observations about stakeholder alignment.",
            "Capture specific onboarding contributions.",
        ],
        "markdown": "## Interview Guide\n- Question list\n- Focus areas",
    }


_INTERVIEW_GUIDE_VALIDATOR = Draft202012Validator(INTERVIEW_GUIDE_SCHEMA)


def test_interview_guide_schema_requires_focus_area_label() -> None:
    payload = deepcopy(_build_interview_guide_payload())
    payload["focus_areas"][0].pop("label")
    with pytest.raises(ValidationError):
        _INTERVIEW_GUIDE_VALIDATOR.validate(payload)


class _FakeResult(ChatCallResult):
    def __init__(self, content: str = "{}") -> None:
        super().__init__(content=content, tool_calls=[], usage={})


def _contains_json_ref(value: Any) -> bool:
    if isinstance(value, dict):
        if "$ref" in value:
            return True
        return any(_contains_json_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_json_ref(item) for item in value)
    return False


def _assert_objects_disallow_additional_properties(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        schema_type = value.get("type")
        if schema_type == "object":
            assert value.get("additionalProperties") is False, (
                f"Schema object at {path} must set additionalProperties to False"
            )
            properties = value.get("properties")
            if isinstance(properties, dict):
                for key, nested in properties.items():
                    _assert_objects_disallow_additional_properties(nested, f"{path}.{key}")

        if "items" in value:
            items = value["items"]
            if isinstance(items, list):
                for index, nested in enumerate(items):
                    _assert_objects_disallow_additional_properties(nested, f"{path}[{index}]")
            else:
                _assert_objects_disallow_additional_properties(items, f"{path}[]")

        for key in ("allOf", "anyOf", "oneOf", "if", "then", "else"):
            if key in value:
                _assert_objects_disallow_additional_properties(value[key], f"{path}.{key}")

    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_objects_disallow_additional_properties(nested, f"{path}[{index}]")


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("streamlit.session_state", {}, raising=False)


def test_extract_vacancy_passes_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(extraction_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(extraction_mod, "get_model_for", lambda *_, **__: "model-extraction")
    extraction_mod.extract_vacancy_structured("Text", "de")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "VacancyExtraction"
    assert schema_cfg["schema"] == VACANCY_EXTRACTION_SCHEMA
    assert not _contains_json_ref(schema_cfg["schema"])
    _assert_objects_disallow_additional_properties(VACANCY_EXTRACTION_SCHEMA)
    assert captured["model"] == "model-extraction"


def test_followups_pass_schema_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(followups_mod, "get_model_for", lambda *_, **__: "model-followups")
    followups_mod.generate_followups({}, "en", vector_store_id="store-id")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "FollowUpQuestions"
    assert schema_cfg["schema"] == FOLLOW_UPS_SCHEMA
    _assert_objects_disallow_additional_properties(FOLLOW_UPS_SCHEMA)
    assert captured["tools"] == [
        {
            "type": "file_search",
            "name": "file_search",
            "vector_store_ids": ["store-id"],
            "file_search": {"vector_store_ids": ["store-id"]},
        }
    ]
    assert captured["tool_choice"] == "auto"
    assert captured["model"] == "model-followups"


def test_followups_without_vector_store(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(followups_mod, "get_model_for", lambda *_, **__: "model-followups")
    followups_mod.generate_followups({}, "de")

    assert captured.get("tools") is None
    assert captured.get("tool_choice") is None
    assert captured["model"] == "model-followups"


def test_followups_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "questions": [
            {
                "field": "company.name",
                "question": "What is the company name?",
                "priority": "critical",
                "suggestions": [],
            }
        ]
    }

    def fake_call(messages: list[dict[str, Any]], **_: Any) -> _FakeResult:
        return _FakeResult(content=json.dumps(payload))

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(followups_mod, "get_model_for", lambda *_, **__: "model-followups")

    result = followups_mod.generate_followups({}, "en")

    assert result == payload


def test_followups_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call(messages: list[dict[str, Any]], **_: Any) -> _FakeResult:
        raise RuntimeError("test failure")

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(followups_mod, "get_model_for", lambda *_, **__: "model-followups")

    result = followups_mod.generate_followups({}, "de")

    assert result == {"questions": []}


def test_profile_summary_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(profile_summary_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(profile_summary_mod, "get_model_for", lambda *_, **__: "model-profile")
    profile_summary_mod.summarize_candidate(
        "CV",
        "en",
        "cand-1",
        job_requirements="Looking for a data engineer with Python, ETL, and stakeholder alignment skills.",
    )

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "CandidateProfileSummary"
    assert schema_cfg["schema"] == PROFILE_SUMMARY_SCHEMA
    _assert_objects_disallow_additional_properties(PROFILE_SUMMARY_SCHEMA)
    assert captured["model"] == "model-profile"


def test_candidate_matching_schema() -> None:
    vacancy = {
        "vacancy_id": "vac-42",
        "requirements": {"hard_skills_required": ["Python"]},
        "position": {"seniority_level": "Senior"},
    }
    candidates = [
        {
            "candidate": {
                "id": "cand-1",
                "name": "A Candidate",
                "location": "Berlin",
                "total_years_experience": 7,
            },
            "skills": [{"name": "Python"}],
            "languages": [{"code": "en"}],
        }
    ]

    payload = matching_mod.match_candidates(vacancy, candidates)
    Draft202012Validator(CANDIDATE_MATCHES_SCHEMA).validate(payload)
    assert payload["candidates"][0]["score"] <= 100
    _assert_objects_disallow_additional_properties(CANDIDATE_MATCHES_SCHEMA)


def test_job_ad_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult(content=json.dumps(_build_job_ad_payload()))

    monkeypatch.setattr(job_ad_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(job_ad_mod, "get_model_for", lambda *_, **__: "model-job-ad")
    job_ad_mod.generate_job_ad({}, "de", tone="casual")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "JobAd"
    assert schema_cfg["schema"] == JOB_AD_SCHEMA
    _assert_objects_disallow_additional_properties(JOB_AD_SCHEMA)
    assert captured["model"] == "model-job-ad"


def _build_job_ad_payload() -> dict[str, Any]:
    return {
        "language": "de",
        "metadata": {"tone": "professional", "target_audience": "Ingenieur:innen"},
        "ad": {
            "title": "Software Engineer (m/w/d)",
            "sections": {
                "overview": "Führe Releases eigenverantwortlich durch und begleite neue Features von der Idee bis zum Launch.",
                "responsibilities": [
                    "Own sprint deliverables",
                    "Collaborate with product",
                    "Coach junior engineers",
                ],
                "requirements": [
                    "5+ years experience",
                    "Deep Python knowledge",
                    "Experience with CI/CD",
                ],
                "benefits": ["Hybrid remote"],
                "compensation_note": "Fair salary band disclosed in offer stage.",
                "how_to_apply": "Apply via our portal with your CV.",
                "equal_opportunity_statement": "We hire without regard to background.",
            },
            "tags": [],
        },
    }


def test_job_ad_generation_rejects_missing_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call(*_args: Any, **_kwargs: Any) -> _FakeResult:
        payload = _build_job_ad_payload()
        payload["metadata"]["target_audience"] = "  "
        payload["ad"]["sections"]["responsibilities"] = ["", " ", " "]
        return _FakeResult(content=json.dumps(payload))

    monkeypatch.setattr(job_ad_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(job_ad_mod, "get_model_for", lambda *_, **__: "model-job-ad")

    with pytest.raises(ValueError):
        job_ad_mod.generate_job_ad({}, "de", tone="casual")


def test_interview_guide_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(interview_mod, "call_chat_api", fake_call)
    monkeypatch.setattr(interview_mod, "get_model_for", lambda *_, **__: "model-interview")
    interview_mod.generate_interview_guide({}, "en")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "InterviewGuide"
    assert schema_cfg["schema"] == INTERVIEW_GUIDE_SCHEMA
    _assert_objects_disallow_additional_properties(INTERVIEW_GUIDE_SCHEMA)
    assert captured["model"] == "model-interview"


def test_interview_guide_sample_payload_validates() -> None:
    """Ensure a representative guide payload passes the JSON schema."""

    payload = _build_interview_guide_payload()
    _INTERVIEW_GUIDE_VALIDATOR.validate(payload)


def test_interview_guide_schema_requires_heading() -> None:
    """Dropping a required metadata field should fail validation."""

    payload = _build_interview_guide_payload()
    payload["metadata"].pop("heading")

    with pytest.raises(ValidationError):
        _INTERVIEW_GUIDE_VALIDATOR.validate(payload)
