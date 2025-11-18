"""Regression tests for NeedAnalysisOutputParser."""

from __future__ import annotations

import json

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
