"""Tests for the disabled ESCO utilities."""

from core import esco_utils as esco


def test_classify_occupation_returns_none() -> None:
    """Occupation classification should be disabled."""

    assert esco.classify_occupation("Software engineer") is None


def test_get_essential_skills_returns_empty() -> None:
    """Essential skill lookups should return an empty list."""

    assert esco.get_essential_skills("http://example.com/occ") == []


def test_lookup_esco_skill_returns_empty() -> None:
    """Skill lookups should be disabled."""

    assert esco.lookup_esco_skill("Python") == {}


def test_normalize_skills_dedupes_locally() -> None:
    """Normalization should trim and deduplicate values locally."""

    out = esco.normalize_skills(["Python", "python ", "", "Docker"])
    assert out == ["Python", "Docker"]
