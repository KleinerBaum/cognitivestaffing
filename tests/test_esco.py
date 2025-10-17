"""Tests for the ESCO utility layer using recorded API fixtures."""

from __future__ import annotations

import json
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
    monkeypatch.delenv("VACAYSER_OFFLINE", raising=False)
    yield
    esco._get_occupation_detail.cache_clear()
    esco._api_lookup_skill.cache_clear()


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
