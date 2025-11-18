"""Regression tests for NeedAnalysisOutputParser."""

from __future__ import annotations

import json

from typing import Any

from llm.output_parsers import NeedAnalysisOutputParser
from models.need_analysis import NeedAnalysisProfile


def _base_payload() -> dict:
    return NeedAnalysisProfile().model_dump()


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

    def _fake_repair_profile_payload(
        data: dict[str, Any], *, errors: Any = None
    ) -> dict[str, Any]:
        repair_called["errors"] = errors
        repaired = json.loads(json.dumps(data))
        repaired["position"]["team_size"] = 7
        return repaired

    monkeypatch.setattr("llm.output_parsers.repair_profile_payload", _fake_repair_profile_payload)

    model, data = parser.parse(json.dumps(payload))

    assert "errors" in repair_called
    assert data["position"]["team_size"] == 7
    assert model.position.team_size == 7
