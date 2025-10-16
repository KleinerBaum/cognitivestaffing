"""Integration-level expectations for disabled ESCO features."""

from __future__ import annotations

import pytest

from core import suggestions
from core.esco_utils import classify_occupation, normalize_skills
from integrations import esco


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    yield
    monkeypatch.delenv("VACAYSER_OFFLINE", raising=False)


def test_search_occupation_returns_match() -> None:
    """Occupation search should return a deterministic match."""

    result = esco.search_occupation("Data Scientist")
    assert result
    assert result["group"] == "Information and communications technology professionals"
    options = esco.search_occupation_options("Data Scientist")
    assert options
    assert options[0]["preferredLabel"]


def test_classify_occupation_keyword_fallback() -> None:
    """Keyword matching should return compatible ESCO group identifiers."""

    result = classify_occupation("Senior Sales Manager")
    assert result
    assert result["group"].casefold() == ("sales, marketing and public relations professionals")


def test_normalize_skills_dedupes_without_esco() -> None:
    """Normalization should work locally without ESCO lookups."""

    out = normalize_skills(["Python", "python", "Management", ""])
    assert out == ["Python", "Management"]


def test_skill_suggestions_group_by_esco_type(monkeypatch):
    """ESCO skill suggestions should map to field buckets by type."""

    monkeypatch.setattr(
        suggestions,
        "classify_occupation",
        lambda title, lang="en": {"uri": "http://example.com/occupation"},
    )
    monkeypatch.setattr(
        suggestions,
        "get_essential_skills",
        lambda uri, lang="en": [
            "Python programming",
            "JIRA software",
            "AWS Certified Solutions Architect",
        ],
    )
    meta_map = {
        "Python programming": {
            "preferredLabel": "Python programming",
            "skillType": "http://data.europa.eu/esco/skill-type/knowledge",
        },
        "JIRA software": {
            "preferredLabel": "JIRA software",
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
        "AWS Certified Solutions Architect": {
            "preferredLabel": "AWS Certified Solutions Architect",
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
        "Customer focus": {
            "preferredLabel": "Customer focus",
            "skillType": "http://data.europa.eu/esco/skill-type/competence",
        },
    }
    monkeypatch.setattr(
        suggestions,
        "lookup_esco_skill",
        lambda name, lang="en": meta_map.get(name, {"preferredLabel": name}),
    )
    monkeypatch.setattr(suggestions, "suggest_skills_for_role", lambda *_, **__: {})

    grouped, error = suggestions.get_skill_suggestions(
        "Engineer",
        missing_skills=["Customer focus"],
    )

    assert error is None
    assert grouped == {
        "hard_skills": {"esco_knowledge": ["Python programming"]},
        "tools_and_technologies": {"esco_tools": ["JIRA software"]},
        "certificates": {"esco_certificates": ["AWS Certified Solutions Architect"]},
        "soft_skills": {"esco_missing_competence": ["Customer focus"]},
    }
