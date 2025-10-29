"""Unit tests for Responses schema helpers."""

from __future__ import annotations

import json

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
    assert logo_schema["type"] == "string"
    assert "format" not in logo_schema
    assert logo_schema.get("pattern") == _URL_PATTERN

    assert company_props["contact_email"] == {"type": "string", "format": "email"}


def test_invalid_type_marker_rejected() -> None:
    """Custom schemas with pseudo-types trigger validation errors."""

    with pytest.raises(ValueError):
        ensure_responses_json_schema({"type": ["string", "uri"]})
