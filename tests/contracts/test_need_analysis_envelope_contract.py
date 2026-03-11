"""Contract tests for NeedAnalysisEnvelope and profile adapter compatibility."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from adapters.profile_to_envelope import adapt_profile_to_envelope
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
