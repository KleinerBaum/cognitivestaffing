"""Validation and defaulting behaviour for NeedAnalysisProfile payloads."""

from __future__ import annotations

from utils.normalization import normalize_profile


def test_missing_required_sections_are_populated() -> None:
    """Normalization should inject required sections and critical keys."""

    payload = {"position": {"job_title": "Engineer"}}

    normalized = normalize_profile(payload)

    for section in (
        "company",
        "position",
        "location",
        "responsibilities",
        "requirements",
        "employment",
        "compensation",
        "process",
        "meta",
    ):
        assert section in normalized

    assert "name" in normalized["company"]


def test_missing_skill_mapping_fields_receive_defaults() -> None:
    """Skill mapping entries should always include their required keys."""

    payload = {
        "company": {"name": "ACME"},
        "requirements": {
            "hard_skills_required": ["Python"],
        },
    }

    normalized = normalize_profile(payload)
    entry = normalized["requirements"]["skill_mappings"]["hard_skills_required"][0]

    assert entry["name"] == "Python"
    assert "normalized_name" in entry
    assert "esco_uri" in entry
    assert "weight" in entry
