import json

import pytest

from core.extraction import InvalidExtractionPayload, mark_low_confidence, parse_structured_payload


def test_parse_structured_payload_with_noise() -> None:
    raw = 'Header\n{"company": {"name": "ACME"}}\nFooter'
    data, recovered, issues = parse_structured_payload(raw)
    assert recovered is True
    assert data["company"]["name"] == "ACME"
    assert any("JSON parsing error" in entry for entry in issues)


def test_parse_structured_payload_invalid() -> None:
    with pytest.raises(InvalidExtractionPayload):
        parse_structured_payload("not json")


def test_parse_structured_payload_reports_invalid_fields() -> None:
    raw = json.dumps({"company": {"contact_email": "invalid"}})
    data, recovered, issues = parse_structured_payload(raw)

    assert recovered is False
    assert "contact_email" not in data.get("company", {})
    assert any("company.contact_email" in entry for entry in issues)


def test_mark_low_confidence_updates_metadata() -> None:
    metadata: dict = {}
    data = {"company": {"name": "ACME"}, "position": {"job_title": "Engineer"}, "tags": [{"value": "A"}]}

    mark_low_confidence(metadata, data)

    field_conf = metadata["field_confidence"]
    assert field_conf["company.name"]["confidence"] == pytest.approx(0.2)
    assert field_conf["position.job_title"]["note"] == "invalid_json_recovery"
    assert metadata["llm_recovery"]["invalid_json"] is True
    assert "tags[0].value" in field_conf
