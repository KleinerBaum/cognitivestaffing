"""Integration-level expectations for disabled ESCO features."""

from __future__ import annotations

import pytest

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
    assert result["group"].casefold() == (
        "sales, marketing and public relations professionals"
    )


def test_normalize_skills_dedupes_without_esco() -> None:
    """Normalization should work locally without ESCO lookups."""

    out = normalize_skills(["Python", "python", "Management", ""])
    assert out == ["Python", "Management"]
