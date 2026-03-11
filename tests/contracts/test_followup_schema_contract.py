from __future__ import annotations

import json

from llm.followup_contract import (
    get_followup_json_schema,
    get_followup_validator,
)
from core.schema_registry import get_canonical_json_schema
from wizard.services import followups as followups_mod


def test_followup_service_schema_matches_response_schema_registry() -> None:
    expected = {
        "name": "followup_questions",
        "schema": get_canonical_json_schema(schema_version="v1", artifact="followups"),
    }

    assert get_followup_json_schema() == expected
    assert followups_mod.FOLLOWUP_JSON_SCHEMA == expected
    assert get_followup_validator().schema == expected["schema"]


def test_followup_parser_contract_snapshot_with_legacy_fields() -> None:
    raw_payload = {
        "questions": [
            {
                "field": "position.context",
                "question": "Please describe role context",
                "priority": "normal",
                "suggestions": ["Distributed team"],
            },
            {
                "field": "compensation.salary_range",
                "question": "What's the salary range?",
                "priority": "critical",
                "suggestions": [],
            },
        ]
    }

    parsed = followups_mod._parse_followup_response(json.dumps(raw_payload))

    assert parsed.fallback_reason is None
    assert parsed.payload == {
        "questions": [
            {
                "field": "position.role_summary",
                "question": "Please describe role context",
                "priority": "normal",
                "suggestions": ["Distributed team"],
            },
            {
                "field": "compensation.salary_min",
                "question": "What's the salary range?",
                "priority": "critical",
                "suggestions": ["What's the salary range?"],
            },
        ]
    }
