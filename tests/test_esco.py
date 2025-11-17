"""Tests for the ESCO utility layer using recorded API fixtures."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from core import esco_utils as esco

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    esco._get_occupation_detail.cache_clear()
    esco._api_lookup_skill.cache_clear()
    esco.clear_streamlit_esco_cache()
    monkeypatch.delenv("VACAYSER_OFFLINE", raising=False)
    yield
    esco._get_occupation_detail.cache_clear()
    esco._api_lookup_skill.cache_clear()
    esco.clear_streamlit_esco_cache()


def test_classify_occupation_from_fixture(monkeypatch):
    """Occupation classification should parse recorded API responses."""

    search_payload = _load_fixture("search_software_engineer.json")
    detail_payload = _load_fixture("occupation_software_developer_en.json")

    def fake_fetch(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if "search" in url:
            return search_payload
        if "resource/occupation" in url and params.get("language") == "en":
            return detail_payload
        raise AssertionError(f"unexpected call: {url}")

    monkeypatch.setattr(esco, "_fetch_json", fake_fetch)

    result = esco.classify_occupation("Software engineer", lang="en")
    assert result == {
        "preferredLabel": "software developer",
        "uri": search_payload["_embedded"]["results"][0]["uri"],
        "group": "Information and communications technology professionals",
    }


def test_get_essential_skills_from_fixture(monkeypatch):
    """Essential skill lookups should surface localized labels."""

    detail_en = _load_fixture("occupation_software_developer_en.json")
    detail_de = _load_fixture("occupation_software_developer_de.json")

    def fake_fetch(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if params.get("language") == "de":
            return detail_de
        return detail_en

    monkeypatch.setattr(esco, "_fetch_json", fake_fetch)

    uri = detail_en["uri"]
    skills_en = esco.get_essential_skills(uri, lang="en")
    skills_de = esco.get_essential_skills(uri, lang="de")

    assert "computer programming" in skills_en
    assert "Computerprogrammierung" in skills_de


def test_normalize_skills_uses_lookup(monkeypatch):
    """Normalization should leverage recorded skill lookups."""

    search_payload = _load_fixture("search_skill_python.json")

    def fake_fetch(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if params.get("text", "").lower() == "python":
            return search_payload
        return {"_embedded": {"results": []}}

    monkeypatch.setattr(esco, "_fetch_json", fake_fetch)

    out = esco.normalize_skills(["python", "Python", " data"], lang="en")
    # ``search_skill_python`` resolves to the canonical label but we prefer a
    # compact human-readable variant for display.
    assert out == ["Python", "data"]


def test_get_essential_skills_falls_back_to_cache(monkeypatch):
    """Essential skill lookup should reuse the offline cache on HTTP errors."""

    monkeypatch.setattr(esco, "_is_offline", lambda: False)
    monkeypatch.setattr(
        esco,
        "_api_essential_skills",
        lambda *_a, **_k: (_ for _ in ()).throw(esco.EscoServiceError("404")),
    )

    uri = "http://data.europa.eu/esco/occupation/12345"
    expected = esco._offline_essential_skills(uri)
    assert expected, "offline cache must provide fallback skills"

    skills = esco.get_essential_skills(uri, lang="en")
    assert skills == expected


def test_get_essential_skills_uses_offline_cache_for_placeholder(monkeypatch, caplog):
    """Placeholder URIs with cached skills must avoid API calls and warnings."""

    monkeypatch.setattr(esco, "_is_offline", lambda: False)

    calls: list[tuple[str, str]] = []

    def fake_api(uri: str, lang: str) -> list[str]:
        calls.append((uri, lang))
        return ["unexpected"]

    monkeypatch.setattr(esco, "_api_essential_skills", fake_api)

    uri = next(iter(esco._SKILLS_BY_URI))
    expected = esco._offline_essential_skills(uri)
    assert expected, "fixture must provide cached skills"

    with caplog.at_level(logging.WARNING, logger="cognitive_needs.esco"):
        skills = esco.get_essential_skills(uri, lang="en")

    assert skills == expected
    assert calls == []
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_cached_classify_reuses_streamlit_cache(monkeypatch, caplog):
    """The Streamlit cache should prevent duplicate ESCO occupation lookups."""

    pytest.importorskip("streamlit")
    esco.clear_streamlit_esco_cache()
    calls: list[str] = []

    def fake_classify(title: str, lang: str = "en") -> Dict[str, str]:
        calls.append(f"{title}:{lang}")
        return {"preferredLabel": title, "uri": f"fake://{title}", "group": "grp"}

    monkeypatch.setattr(esco, "classify_occupation", fake_classify)

    with caplog.at_level(logging.INFO, logger="cognitive_needs.esco"):
        first = esco.cached_classify_occupation("Data Scientist", lang="en")
        again = esco.cached_classify_occupation("Data Scientist", lang="en")

    assert first == again
    assert calls == ["Data Scientist:en"]
    assert any("cache hit" in record.getMessage() for record in caplog.records)


def test_cached_skills_reuses_streamlit_cache(monkeypatch, caplog):
    """The Streamlit cache must reuse essential skill lookups for identical URIs."""

    pytest.importorskip("streamlit")
    esco.clear_streamlit_esco_cache()
    calls: list[str] = []

    def fake_skills(uri: str, lang: str = "en") -> list[str]:
        calls.append(f"{uri}:{lang}")
        return [f"skill-{lang}"]

    monkeypatch.setattr(esco, "get_essential_skills", fake_skills)

    with caplog.at_level(logging.INFO, logger="cognitive_needs.esco"):
        first = esco.cached_get_essential_skills("fake://uri", lang="en")
        again = esco.cached_get_essential_skills("fake://uri", lang="en")

    assert first == again == ["skill-en"]
    assert calls == ["fake://uri:en"]
    assert any("cache hit" in record.getMessage() for record in caplog.records)
