from __future__ import annotations

import json

from utils.json_repair import JsonRepairStatus
from wizard.services import followups as followups_mod


def _payload() -> dict[str, object]:
    return {
        "questions": [
            {
                "field": "company.name",
                "question": "What is the company name?",
                "priority": "critical",
                "suggestions": ["ACME"],
            }
        ]
    }


def test_parse_followups_valid_json() -> None:
    result = followups_mod._parse_followup_response(json.dumps(_payload()))
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["field"] == "company.name"


def test_parse_followups_json_fence() -> None:
    fenced = f"```json\n{json.dumps(_payload())}\n```"
    result = followups_mod._parse_followup_response(fenced)
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["question"].startswith("What is")


def test_parse_followups_trailing_commas() -> None:
    trailing = (
        '{"questions": [{"field": "company.name", "question": "Name?", '
        '"priority": "critical", "suggestions": ["ACME",],},],}'
    )
    result = followups_mod._parse_followup_response(trailing)
    assert result.fallback_reason is None
    assert result.repair_status is JsonRepairStatus.REPAIRED


def test_parse_followups_leading_prose() -> None:
    prose = f"Here are the questions:\n{json.dumps(_payload())}"
    result = followups_mod._parse_followup_response(prose)
    assert result.fallback_reason is None
    assert result.payload["questions"][0]["priority"] == "critical"


def test_parse_followups_missing_required_key() -> None:
    invalid = {
        "questions": [
            {
                "field": "company.name",
                "priority": "critical",
                "suggestions": ["ACME"],
            }
        ]
    }
    result = followups_mod._parse_followup_response(json.dumps(invalid))
    assert result.fallback_reason == "schema_invalid"
    assert result.error_reason == "schema_invalid"
    assert result.validation_errors


def test_parse_followups_deduplicates_fields() -> None:
    payload = {
        "questions": [
            {
                "field": "company.name",
                "question": "What is the company name?",
                "priority": "critical",
                "suggestions": ["ACME"],
            },
            {
                "field": "company.name",
                "question": "Please confirm company name.",
                "priority": "normal",
                "suggestions": ["ACME GmbH"],
            },
        ]
    }

    result = followups_mod._parse_followup_response(json.dumps(payload))

    assert result.fallback_reason is None
    questions = result.payload["questions"]
    assert len(questions) == 1
    assert questions[0]["field"] == "company.name"
    assert questions[0]["question"] == "What is the company name?"


def test_prioritize_followups_prefers_low_confidence_critical_fields() -> None:
    profile = {
        "company": {"name": "ACME"},
        "location": {"country": "DE"},
        "meta": {
            "field_metadata": {
                "location.country": {
                    "source": "heuristic",
                    "confidence": 0.2,
                    "confirmed": False,
                },
                "company.name": {
                    "source": "user",
                    "confidence": 1.0,
                    "confirmed": True,
                    "evidence_snippet": "ACME",
                },
            }
        },
    }
    questions = [
        {
            "field": "company.name",
            "question": "Confirm company name",
            "priority": "critical",
            "suggestions": ["ACME"],
        },
        {
            "field": "location.country",
            "question": "Confirm country",
            "priority": "normal",
            "suggestions": ["DE"],
        },
    ]

    result = followups_mod._prioritize_heuristic_followups(questions, profile=profile)

    assert result[0]["field"] == "location.country"


def test_prioritize_followups_is_deterministic_for_same_profile() -> None:
    profile = {
        "company": {"name": "ACME"},
        "meta": {"field_metadata": {}},
    }
    questions = [
        {"field": "company.name", "question": "Confirm company name", "priority": "normal"},
        {"field": "company.name", "question": "confirm company name", "priority": "normal"},
        {"field": "location.country", "question": "Confirm country", "priority": "normal"},
    ]

    first = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)
    second = followups_mod._prioritize_heuristic_followups(list(questions), profile=profile)

    assert [item["field"] + ":" + item["question"] for item in first] == [
        item["field"] + ":" + item["question"] for item in second
    ]
