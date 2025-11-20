"""Tests for schema repair during structured payload parsing."""

from __future__ import annotations

from core.extraction import parse_structured_payload


def test_parse_structured_payload_adds_missing_sections_and_defaults() -> None:
    """Missing sections should be filled and reported as issues."""

    payload, recovered, issues = parse_structured_payload('{"position": {"job_title": "Developer"}}')

    assert recovered is False
    assert payload["position"]["job_title"] == "Developer"
    assert "company" in payload
    assert "name" in payload["company"]
    assert any(entry.startswith("company:") or entry.startswith("company ") or entry.startswith("company.") for entry in issues)
    assert any("company.name" in entry for entry in issues)
