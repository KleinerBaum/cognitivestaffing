import json

import pytest

from core.extraction import InvalidExtractionPayload, mark_low_confidence, parse_structured_payload
from core.schema import process_extracted_profile


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
    assert data.get("company", {}).get("contact_email") is None
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


def test_process_extracted_profile_splits_skill_requirements() -> None:
    """Mixed skill pools should map into the dedicated requirement buckets."""

    payload = {
        "skills": {
            "must_have": ["Python", "Communication", "AWS"],
            "nice_to_have": ["Team leadership", "AWS Certified Developer"],
        }
    }

    profile = process_extracted_profile(payload)
    requirements = profile.requirements

    assert "Python" in requirements.hard_skills_required
    assert "AWS" in requirements.tools_and_technologies
    assert "Communication" in requirements.soft_skills_required
    assert "Team leadership" in requirements.soft_skills_optional
    assert "AWS Certified Developer" in requirements.certifications
    assert "Communication" not in requirements.hard_skills_required
    assert "AWS" not in requirements.hard_skills_required
