"""Tests for ESCO integration wrapper with offline support."""

import importlib


def test_offline_fallback(monkeypatch):
    """search_occupation and enrich_skills use offline JSON when enabled."""
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)
    occ = module.search_occupation("Software Engineer")
    assert occ["uri"] == "http://data.europa.eu/esco/occupation/12345"
    skills = module.enrich_skills(occ["uri"])
    assert "Python" in skills


def test_offline_generic_skills_filtered(monkeypatch):
    """Generic skills like 'Communication' are filtered out."""
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)
    occ = module.search_occupation("Sales Representative")
    skills = module.enrich_skills(occ["uri"])
    assert "Communication" not in skills


def test_offline_unknown_title(monkeypatch):
    """Unknown titles return empty dict and no crash."""
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)
    occ = module.search_occupation("Unknown Role")
    assert occ == {}


def test_offline_options(monkeypatch):
    """Offline occupation option search returns at most one cached entry."""
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)
    opts = module.search_occupation_options("Software Engineer")
    assert isinstance(opts, list)
    assert opts and opts[0]["uri"].startswith("http://data.europa.eu/esco/occupation/")


def test_offline_missing_skills_warning(monkeypatch, caplog):
    """Missing offline skills trigger a warning and return empty list."""
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)
    with caplog.at_level("WARNING"):
        skills = module.enrich_skills("unknown-uri")
    assert skills == []
    assert any("No offline ESCO skills" in r.message for r in caplog.records)


def test_online_delegation(monkeypatch):
    """Wrapper delegates to core.esco_utils when not offline."""
    monkeypatch.delenv("VACAYSER_OFFLINE", raising=False)
    module = importlib.import_module("integrations.esco")
    importlib.reload(module)

    calls = {}

    def fake_classify(title: str, lang: str = "en") -> dict:
        calls["classify"] = (title, lang)
        return {"uri": "x"}

    def fake_skills(uri: str, lang: str = "en") -> list[str]:
        calls["skills"] = (uri, lang)
        return ["A"]

    def fake_options(title: str, lang: str = "en", limit: int = 5) -> list[dict]:
        calls["options"] = (title, lang, limit)
        return [{"uri": "y", "preferredLabel": "Dev", "group": "IT"}]

    monkeypatch.setattr(module.esco_utils, "classify_occupation", fake_classify)
    monkeypatch.setattr(module.esco_utils, "get_essential_skills", fake_skills)
    monkeypatch.setattr(module.esco_utils, "search_occupations", fake_options)

    occ = module.search_occupation("Dev", "de")
    skills = module.enrich_skills("u", "de")
    opts = module.search_occupation_options("Dev", "de", limit=7)

    assert calls["classify"] == ("Dev", "de")
    assert calls["skills"] == ("u", "de")
    assert calls["options"] == ("Dev", "de", 7)
    assert occ == {"uri": "x"}
    assert skills == ["A"]
    assert opts == [{"uri": "y", "preferredLabel": "Dev", "group": "IT"}]
