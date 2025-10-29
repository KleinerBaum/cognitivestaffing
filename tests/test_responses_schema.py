"""Unit tests for Responses schema helpers."""

from __future__ import annotations

import pytest

from core.schema import build_need_analysis_responses_schema, ensure_responses_json_schema
from openai_utils.api import build_need_analysis_json_schema_payload


def test_url_email_formats_ok() -> None:
    """Need analysis schema maps URL/email fields to canonical formats."""

    schema = build_need_analysis_responses_schema()
    company_props = schema["properties"]["company"]["properties"]

    assert company_props["logo_url"] == {"type": "string", "format": "uri"}
    assert company_props["contact_email"] == {"type": "string", "format": "email"}

    payload = build_need_analysis_json_schema_payload()
    assert payload["name"] == "need_analysis_profile"
    assert payload["schema"] == schema


def test_invalid_type_marker_rejected() -> None:
    """Custom schemas with pseudo-types trigger validation errors."""

    with pytest.raises(ValueError):
        ensure_responses_json_schema({"type": ["string", "uri"]})
