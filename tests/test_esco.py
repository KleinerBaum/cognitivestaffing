"""Tests for the offline ESCO utilities."""

from core import esco_utils as esco


def test_classify_occupation_offline_match() -> None:
    """Occupation classification should use the offline cache."""

    result = esco.classify_occupation("Software engineer")
    assert result
    assert result["group"] == "Information and communications technology professionals"


def test_get_essential_skills_returns_offline_data() -> None:
    """Essential skill lookups should return deterministic cached data."""

    occupation = esco.classify_occupation("Software engineer")
    assert occupation
    skills = esco.get_essential_skills(occupation["uri"])
    assert skills
    assert "Python" in skills


def test_lookup_esco_skill_normalizes() -> None:
    """Skill lookups should normalize labels locally."""

    assert esco.lookup_esco_skill("Python") == {"preferredLabel": "Python"}


def test_normalize_skills_dedupes_locally() -> None:
    """Normalization should trim and deduplicate values locally."""

    out = esco.normalize_skills(["Python", "python ", "", "Docker"])
    assert out == ["Python", "Docker"]
