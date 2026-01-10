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
