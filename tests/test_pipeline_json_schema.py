"""Ensure high-level pipelines pass JSON schema configuration to call_chat_api."""

from __future__ import annotations

from typing import Any

import pytest

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


class _FakeResult(ChatCallResult):
    def __init__(self) -> None:
        super().__init__(content="{}", tool_calls=[], usage={})


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("streamlit.session_state", {}, raising=False)


def test_extract_vacancy_passes_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(extraction_mod, "call_chat_api", fake_call)
    extraction_mod.extract_vacancy_structured("Text", "de")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "VacancyExtraction"
    assert schema_cfg["schema"] == VACANCY_EXTRACTION_SCHEMA


def test_followups_pass_schema_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    followups_mod.generate_followups({}, "en", vector_store_id="store-id")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "FollowUpQuestions"
    assert schema_cfg["schema"] == FOLLOW_UPS_SCHEMA
    assert captured["tools"] == [{"type": "file_search", "vector_store_ids": ["store-id"]}]


def test_followups_without_vector_store(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(followups_mod, "call_chat_api", fake_call)
    followups_mod.generate_followups({}, "de")

    assert captured.get("tools") is None


def test_profile_summary_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(profile_summary_mod, "call_chat_api", fake_call)
    profile_summary_mod.summarize_candidate("CV", "en", "cand-1")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "CandidateProfileSummary"
    assert schema_cfg["schema"] == PROFILE_SUMMARY_SCHEMA


def test_candidate_matching_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(matching_mod, "call_chat_api", fake_call)
    matching_mod.match_candidates({}, [])

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "CandidateMatches"
    assert schema_cfg["schema"] == CANDIDATE_MATCHES_SCHEMA


def test_job_ad_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(job_ad_mod, "call_chat_api", fake_call)
    job_ad_mod.generate_job_ad({}, "de", tone="casual")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "JobAd"
    assert schema_cfg["schema"] == JOB_AD_SCHEMA


def test_interview_guide_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> _FakeResult:
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(interview_mod, "call_chat_api", fake_call)
    interview_mod.generate_interview_guide({}, "en")

    schema_cfg = captured.get("json_schema")
    assert schema_cfg["name"] == "InterviewGuide"
    assert schema_cfg["schema"] == INTERVIEW_GUIDE_SCHEMA
