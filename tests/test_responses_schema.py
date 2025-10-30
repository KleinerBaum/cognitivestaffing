"""Unit tests for Responses schema helpers."""

from __future__ import annotations

import json
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


def _assert_all_properties_required(node: Mapping[str, Any]) -> None:
    if not isinstance(node, Mapping):
        return

    if node.get("type") == "object" and "properties" in node:
        properties = node["properties"]
        required = node.get("required")
        assert isinstance(required, list), "Every object schema must define required"
        assert sorted(required) == sorted(properties), "Required keys must cover all properties"
        for child in properties.values():
            if isinstance(child, Mapping):
                _assert_all_properties_required(child)

    if node.get("type") == "array" and isinstance(node.get("items"), Mapping):
        _assert_all_properties_required(node["items"])

    if isinstance(node.get("anyOf"), list):
        for option in node["anyOf"]:
            if isinstance(option, Mapping):
                _assert_all_properties_required(option)


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


def test_responses_schema_marks_required_and_allows_null_for_optional_fields() -> None:
    """Responses schema enforces strict required lists while tolerating null optionals."""

    schema = build_need_analysis_responses_schema()

    _assert_all_properties_required(schema)

    company_props = schema["properties"]["company"]["properties"]
    assert _allows_null(company_props["name"])

    employment_props = schema["properties"]["employment"]["properties"]
    assert _allows_null(employment_props["travel_required"])

    stakeholder_email = schema["properties"]["process"]["properties"]["stakeholders"]["items"]["properties"]["email"]
    assert _allows_null(stakeholder_email)
