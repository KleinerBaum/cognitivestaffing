from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator

from core.schema import ALL_FIELDS
from core.schema_registry import (
    adapt_payload,
    get_allowed_adapter_paths,
    get_canonical_json_schema,
    get_canonical_model,
)
from models.need_analysis_v2 import NeedAnalysisV2


def _collect_leaf_fields(schema: Mapping[str, Any], prefix: str = "") -> set[str]:
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return set()

    fields: set[str] = set()
    for key, value in properties.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue

        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        nested_props = value.get("properties")
        if isinstance(nested_props, Mapping) and nested_props:
            fields.update(_collect_leaf_fields(value, path))
        else:
            fields.add(path)
    return fields


def test_registry_v1_model_and_schema_leaf_fields_match() -> None:
    schema = get_canonical_json_schema(schema_version="v1", artifact="need_analysis")
    schema_fields = _collect_leaf_fields(schema)

    # ``business_context.source_confidence`` remains model-only metadata and is
    # intentionally excluded from the extraction/Responses schema.
    expected_model_fields = set(ALL_FIELDS) - {"business_context.source_confidence"}

    assert schema_fields == expected_model_fields


def test_registry_v2_model_and_schema_top_level_fields_match() -> None:
    schema = get_canonical_json_schema(schema_version="v2", artifact="need_analysis")
    model_cls = get_canonical_model("v2")

    schema_top_level = set(schema.get("properties", {}).keys())
    model_top_level = set(model_cls.model_fields.keys())

    assert schema_top_level == model_top_level


def test_registry_exposes_explicit_adapter_paths() -> None:
    assert get_allowed_adapter_paths() == (("v1", "v2"),)


def test_v1_to_v2_adapter_roundtrip_export_payload_matches_v2_schema() -> None:
    v1_payload = {
        "company": {"name": "Acme GmbH", "industry": "SaaS"},
        "position": {"job_title": "Software Engineer", "role_summary": "Build APIs"},
        "meta": {
            "field_metadata": {
                "role.title": {
                    "source": "heuristic",
                    "confidence": 0.3,
                    "confirmed": False,
                    "evidence_snippet": "Engineer",
                }
            }
        },
    }

    converted = adapt_payload(v1_payload, source_version="v1", target_version="v2")

    assert isinstance(converted, NeedAnalysisV2)

    export_payload = converted.export_input(artifact_key="job_ad_markdown")
    schema = get_canonical_json_schema(schema_version="v2", artifact="need_analysis")
    Draft202012Validator(schema).validate(export_payload)
