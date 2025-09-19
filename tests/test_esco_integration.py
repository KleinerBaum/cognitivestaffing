"""Tests for the disabled ESCO integration wrapper."""

from integrations import esco


def test_search_returns_empty_results() -> None:
    """Search helpers should return empty data structures."""

    assert esco.search_occupation("Software Engineer") == {}
    assert esco.search_occupation_options("Software Engineer") == []


def test_enrich_skills_returns_empty(caplog) -> None:
    """Skill enrichment should be disabled."""

    with caplog.at_level("INFO"):
        assert esco.enrich_skills("http://example.com/occ") == []
        assert any(
            "Skipping ESCO skill enrichment" in r.message for r in caplog.records
        )
