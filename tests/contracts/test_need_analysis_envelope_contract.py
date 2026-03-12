"""Contract tests for NeedAnalysisEnvelope and profile adapter compatibility."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from adapters.profile_to_envelope import adapt_profile_to_envelope, create_shadow_mode_snapshot
from models.need_analysis import NeedAnalysisProfile
from models.need_analysis_envelope import NeedAnalysisEnvelope


SCHEMA_PATH = Path("schema/need_analysis_envelope.schema.json")


def _load_schema() -> dict[str, object]:
    loaded = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_envelope_schema_has_minimal_required_structure() -> None:
    schema = _load_schema()

    required_raw = schema.get("required")
    assert isinstance(required_raw, list)
    required = set(required_raw)
    assert required == {"schema_version", "facts", "inferences", "gaps", "plan", "risks", "evidence"}


def test_adapter_output_matches_schema_for_minimal_profile() -> None:
    validator = Draft7Validator(_load_schema())

    envelope = adapt_profile_to_envelope(NeedAnalysisProfile())
    payload = envelope.model_dump(mode="json")

    errors = list(validator.iter_errors(payload))
    assert not errors


def test_adapter_remains_backward_compatible_without_meta_field_metadata() -> None:
    legacy_payload = {
        "schema_version": 2,
        "company": {"name": "Acme"},
    }

    envelope = adapt_profile_to_envelope(legacy_payload)

    assert isinstance(envelope, NeedAnalysisEnvelope)
    assert envelope.evidence == []
    assert envelope.facts["company"]["name"] == "Acme"


def test_envelope_schema_round_trip_for_shadow_snapshot() -> None:
    validator = Draft7Validator(_load_schema())

    envelope = create_shadow_mode_snapshot(
        NeedAnalysisProfile(),
        trigger="step_save",
        step="hiring_goal",
    )
    payload = envelope.model_dump(mode="json")

    errors = list(validator.iter_errors(payload))
    assert not errors

    reloaded = NeedAnalysisEnvelope.model_validate(payload)
    assert reloaded.plan
    assert reloaded.plan[0].trigger == "step_save"
    assert reloaded.plan[0].step == "hiring_goal"


def test_shadow_snapshot_example_payload_shape() -> None:
    """Document an example envelope payload emitted in shadow mode."""

    snapshot = create_shadow_mode_snapshot(
        {
            "company": {"name": "Acme"},
            "position": {"job_title": "Platform Engineer"},
        },
        trigger="extraction_complete",
    ).model_dump(mode="json")

    assert snapshot["facts"]["company"]["name"] == "Acme"
    assert snapshot["facts"]["position"]["job_title"] == "Platform Engineer"
    assert snapshot["plan"] == [
        {
            "action": "snapshot",
            "status": "done",
            "mode": "shadow",
            "trigger": "extraction_complete",
            "step": "",
        }
    ]
