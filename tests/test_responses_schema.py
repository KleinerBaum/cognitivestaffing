"""Unit tests for Responses schema helpers."""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any

import pytest

from core.schema import (
    _URL_PATTERN,
    build_need_analysis_responses_schema,
    ensure_responses_json_schema,
)
from openai_utils.api import build_need_analysis_json_schema_payload


def test_no_unsupported_string_formats_in_responses_schema() -> None:
    """Need analysis schema no longer emits unsupported string formats."""

    schema = build_need_analysis_responses_schema()

    assert '"format": "uri"' not in json.dumps(schema, sort_keys=True)

    payload = build_need_analysis_json_schema_payload()
    assert payload["name"] == "need_analysis_profile"
    assert payload["schema"] == schema


def test_logo_url_uses_pattern_instead_of_format() -> None:
    """URL fields rely on patterns rather than unsupported format markers."""

    schema = build_need_analysis_responses_schema()
    company_props = schema["properties"]["company"]["properties"]

    logo_schema = company_props["logo_url"]
    logo_type = logo_schema["type"]
    if isinstance(logo_type, list):
        assert set(logo_type) == {"string", "null"}
    else:
        assert logo_type == "string"
    assert "format" not in logo_schema
    assert logo_schema.get("pattern") == _URL_PATTERN

    email_schema = company_props["contact_email"]
    assert email_schema.get("format") == "email"
    email_type = email_schema.get("type")
    if isinstance(email_type, list):
        assert set(email_type) == {"string", "null"}
    else:
        assert email_type == "string"


def test_invalid_type_marker_rejected() -> None:
    """Custom schemas with pseudo-types trigger validation errors."""

    with pytest.raises(ValueError):
        ensure_responses_json_schema({"type": ["string", "uri"]})


def test_unique_items_pruned_from_responses_schema() -> None:
    """Responses schemas drop unsupported ``uniqueItems`` markers."""

    sanitized = ensure_responses_json_schema(
        {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                }
            },
        }
    )

    assert "uniqueItems" not in sanitized["properties"]["tags"]


def test_ensure_responses_schema_sets_draft_and_required_keys() -> None:
    """Responses schema helper enforces Draft-07 and required arrays."""

    sanitized = ensure_responses_json_schema({"type": "object", "properties": {"foo": {"type": "string"}}})

    assert sanitized["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert sanitized["required"] == []


def _allows_null(node: Mapping[str, Any]) -> bool:
    marker = node.get("type")
    if marker == "null":
        return True
    if isinstance(marker, list):
        return "null" in marker
    if isinstance(marker, str):
        return False
    any_of = node.get("anyOf")
    if isinstance(any_of, list):
        return any(isinstance(option, Mapping) and option.get("type") == "null" for option in any_of)
    return False


def test_responses_schema_respects_required_fields_from_model() -> None:
    """Responses schema keeps only model-required properties in ``required`` lists."""

    schema = build_need_analysis_responses_schema()

    company_required = schema["properties"]["company"].get("required")
    position_required = schema["properties"]["position"].get("required")
    assert company_required == []
    assert position_required == []

    stakeholder_required = schema["properties"]["process"]["properties"]["stakeholders"]["items"].get("required")
    assert stakeholder_required == ["name", "role"]

    phase_required = schema["properties"]["process"]["properties"]["phases"]["items"].get("required")
    assert phase_required == ["name"]

    employment_props = schema["properties"]["employment"]["properties"]
    assert _allows_null(employment_props["travel_required"])

    stakeholder_email = schema["properties"]["process"]["properties"]["stakeholders"]["items"]["properties"]["email"]
    assert _allows_null(stakeholder_email)


def test_need_analysis_schema_file_in_sync() -> None:
    """The checked-in NeedAnalysis schema must match the generated version."""

    repo_schema = json.loads(Path("schema/need_analysis.schema.json").read_text())
    generated = build_need_analysis_responses_schema()

    assert repo_schema == generated, (
        "NeedAnalysis schema drift detected. Run `python scripts/propagate_schema.py --apply`."
    )


def test_need_analysis_schema_can_be_limited_to_sections() -> None:
    """Schema builder can return a trimmed set of NeedAnalysis sections."""

    trimmed = build_need_analysis_responses_schema(sections=["company", "position"])

    assert set(trimmed["properties"]) == {"company", "position"}
    assert set(trimmed.get("required") or []) <= {"company", "position"}
    assert "location" not in trimmed["properties"]
