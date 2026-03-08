"""Regression tests for NeedAnalysisOutputParser."""

from __future__ import annotations

import json

from typing import Any

import pytest

from llm.output_parsers import NeedAnalysisOutputParser, NeedAnalysisParserError
from models.need_analysis import NeedAnalysisProfile


def _base_payload() -> dict:
    payload = NeedAnalysisProfile().model_dump()
    payload.setdefault("position", {})["job_title"] = "Platform Engineer"
    payload.setdefault("company", {})["name"] = "Example GmbH"
    payload.setdefault("location", {})["primary_city"] = "Berlin"
    payload.setdefault("company", {})["website"] = "https://example.com"
    payload.setdefault("company", {})["contact_email"] = "jobs@example.com"
    payload.setdefault("requirements", {})["hard_skills_required"] = ["Python"]
    payload.setdefault("requirements", {})["soft_skills_required"] = ["Communication"]
    payload.setdefault("responsibilities", {})["items"] = [
        "Own onboarding for new partners",
        "Coordinate milestones",
        "Report progress",
    ]
    payload.setdefault("company", {})["culture"] = "Collaborative and transparent"
    payload.setdefault("process", {})["recruitment_timeline"] = "3 interviews over two weeks"
    return payload


def test_parser_converts_empty_interview_stage_list_to_none() -> None:
    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["process"]["interview_stages"] = []

    model, data = parser.parse(json.dumps(payload))

    assert data["process"]["interview_stages"] is None
    assert model.process.interview_stages is None


def test_parser_converts_single_stage_list_to_int() -> None:
    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["process"]["interview_stages"] = [3]

    model, data = parser.parse(json.dumps(payload))

    assert data["process"]["interview_stages"] == 3
    assert model.process.interview_stages == 3


def test_parser_repairs_invalid_payload(monkeypatch) -> None:
    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["position"]["team_size"] = "invalid"

    repair_called: dict[str, object] = {}

    def _fake_repair_profile_payload(data: dict[str, Any], *, errors: Any = None) -> dict[str, Any]:
        repair_called["errors"] = errors
        repaired = json.loads(json.dumps(data))
        repaired["position"]["team_size"] = 7
        team_block = repaired.setdefault("team", {})
        team_block["headcount_target"] = 7
        return repaired

    monkeypatch.setattr("llm.output_parsers.repair_profile_payload", _fake_repair_profile_payload)

    model, data = parser.parse(json.dumps(payload))

    assert "errors" in repair_called
    assert data["team"]["headcount_target"] == 7
    assert model.team.headcount_target == 7


def test_parser_drops_invalid_fields_to_salvage_payload() -> None:
    """Invalid scalar fields should be pruned instead of discarding the profile."""

    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["compensation"]["salary_min"] = "invalid"

    model, data = parser.parse(json.dumps(payload))

    assert data["compensation"].get("salary_min") is None
    assert model.compensation.salary_min is None


def test_parser_errors_when_critical_sections_missing() -> None:
    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["responsibilities"]["items"] = []

    with pytest.raises(NeedAnalysisParserError):
        parser.parse(json.dumps(payload))


def test_parser_errors_when_business_critical_sections_missing() -> None:
    """Business-critical missing fields should trigger missing-section retries."""

    parser = NeedAnalysisOutputParser()
    payload = _base_payload()
    payload["position"]["job_title"] = None
    payload["company"]["name"] = None
    payload["location"]["primary_city"] = ""
    payload["company"]["website"] = None
    payload["company"]["contact_email"] = None
    payload["requirements"]["hard_skills_required"] = []
    payload["requirements"]["soft_skills_required"] = []

    with pytest.raises(NeedAnalysisParserError) as exc_info:
        parser.parse(json.dumps(payload))

    errors = exc_info.value.errors or []
    locations = {tuple(error.get("loc", ())) for error in errors}
    assert ("position", "job_title") in locations
    assert ("company", "name") in locations
    assert ("location", "primary_city") in locations
    assert ("company", "website") in locations
    assert ("company", "contact_email") in locations
    assert ("requirements", "hard_skills_required") in locations
    assert ("requirements", "soft_skills_required") in locations
