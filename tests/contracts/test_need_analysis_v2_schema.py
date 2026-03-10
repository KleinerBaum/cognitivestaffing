"""Contract tests for Need Analysis V2 schema and decision-gating."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from adapters.v1_to_v2 import adapt_v1_to_v2
from models.decision_card import DecisionCard
from models.need_analysis_v2 import NeedAnalysisV2


SCHEMA_PATH = Path("schema/need_analysis_v2.schema.json")


def _load_schema() -> dict[str, object]:
    loaded = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_schema_has_required_top_level_blocks() -> None:
    schema = _load_schema()
    required_raw = schema["required"]
    assert isinstance(required_raw, list)
    required = set(required_raw)
    assert required == {
        "intake",
        "role",
        "work",
        "requirements",
        "constraints",
        "selection",
        "evidence",
        "open_decisions",
        "warnings",
    }


def test_decision_state_enum_is_enforced_in_schema() -> None:
    schema = _load_schema()
    validator = Draft202012Validator(schema)

    payload = NeedAnalysisV2().model_dump(mode="json")
    payload["open_decisions"] = [
        {
            "decision_id": "d1",
            "title": "Decision",
            "field_path": "role.title",
            "decision_state": "invalid",
            "proposed_value": "Engineer",
            "rationale": "n/a",
        }
    ]

    errors = list(validator.iter_errors(payload))
    assert errors
    assert any("decision_state" in ".".join(str(part) for part in error.absolute_path) for error in errors)


def test_decision_state_enum_is_enforced_in_model() -> None:
    with pytest.raises(ValueError):
        DecisionCard(
            decision_id="d1",
            title="Decision",
            field_path="role.title",
            decision_state="invalid",  # type: ignore[arg-type]
            proposed_value="Engineer",
            rationale="n/a",
        )


def test_export_input_contains_only_confirmed_decisions() -> None:
    profile = NeedAnalysisV2(
        open_decisions=[
            DecisionCard(
                decision_id="1",
                title="A",
                field_path="role.title",
                decision_state="confirmed",
                proposed_value="Senior Engineer",
                rationale="approved",
            ),
            DecisionCard(
                decision_id="2",
                title="B",
                field_path="constraints.salary_min",
                decision_state="proposed",
                proposed_value=70000,
                rationale="pending",
            ),
        ]
    )

    export_payload = profile.export_input()

    assert len(export_payload["open_decisions"]) == 1
    assert export_payload["open_decisions"][0]["decision_state"] == "confirmed"


def test_v1_adapter_marks_undecided_items_as_proposed() -> None:
    v1_payload = {
        "meta": {
            "field_metadata": {
                "company.name": {
                    "source": "heuristic",
                    "confidence": 0.42,
                    "confirmed": False,
                    "evidence_snippet": "Acme GmbH",
                }
            }
        }
    }

    converted = adapt_v1_to_v2(v1_payload)

    assert converted.open_decisions
    assert converted.open_decisions[0].decision_state == "proposed"
    assert "Nicht entschieden" in converted.open_decisions[0].rationale
