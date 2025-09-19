"""Integration-level expectations for disabled ESCO features."""

from core.esco_utils import normalize_skills
from integrations import esco


def test_search_occupation_returns_empty() -> None:
    """Occupation search should return an empty mapping."""

    assert esco.search_occupation("Engineer") == {}
    assert esco.search_occupation_options("Engineer") == []


def test_normalize_skills_dedupes_without_esco() -> None:
    """Normalization should work locally without ESCO lookups."""

    out = normalize_skills(["Python", "python", "Management", ""])
    assert out == ["Python", "Management"]
