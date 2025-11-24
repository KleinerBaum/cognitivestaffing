"""Skill requirement classification and splitting tests."""

from __future__ import annotations

from typing import Dict

from pytest import MonkeyPatch

import core.schema as schema


def test_skill_classification_and_splitting(monkeypatch: MonkeyPatch) -> None:
    """Ensure mixed requirements land in the correct schema buckets."""

    esco_meta: Dict[str, Dict[str, str]] = {
        "Python": {"preferredLabel": "Python", "skillType": "http://data.europa.eu/esco/skill-type/skill"},
        "Teamwork": {"preferredLabel": "Teamwork", "skillType": "http://data.europa.eu/esco/skill-type/competence"},
        "AWS Certified Solutions Architect": {
            "preferredLabel": "AWS Certified Solutions Architect",
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
    }

    monkeypatch.setattr(
        schema,
        "lookup_esco_skill",
        lambda term, lang="en": esco_meta.get(str(term).strip(), {"preferredLabel": term}),
    )

    payload = {
        "skills": {
            "must_have": [
                "Python, Java and SQL",
                "English and German",
                "Project management",
                "AWS Certified Solutions Architect",
                "Teamwork",
            ],
            "nice_to_have": ["Docker & Kubernetes"],
        }
    }

    normalized = schema.canonicalize_profile_payload(payload)["requirements"]

    assert set(normalized["languages_required"]) == {"English", "German"}
    assert "English and German" not in normalized["languages_required"]

    tools = normalized["tools_and_technologies"]
    assert {"Python", "Java", "SQL", "Docker", "Kubernetes"}.issubset(set(tools))

    assert normalized["certifications"] == ["AWS Certified Solutions Architect"]
    assert "Teamwork" in normalized["soft_skills_required"]
    assert "Project management" in normalized["hard_skills_required"]
