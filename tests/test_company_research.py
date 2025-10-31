"""Tests for company website research helpers."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Any, Sequence, cast

import requests
import pytest

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from constants.keys import StateKeys
from ingest.types import build_plain_text_document
from wizard import (
    _CompanySectionConfig,
    _candidate_company_page_urls,
    _bulk_fetch_company_sections,
    _enrich_company_profile_from_about,
    _enrich_company_profile_via_web,
    _extract_company_size,
    _fetch_company_page,
    _load_company_page_section,
    _normalise_company_base_url,
    _store_company_page_section,
)


pytestmark = pytest.mark.integration
from models.need_analysis import NeedAnalysisProfile


def test_normalise_company_base_url() -> None:
    """The company URL normaliser should add missing schema and slashes."""

    assert _normalise_company_base_url("https://example.com") == "https://example.com/"
    assert _normalise_company_base_url("www.example.com") == "https://www.example.com/"
    assert _normalise_company_base_url("https://example.com/de") == "https://example.com/de/"
    assert _normalise_company_base_url("") is None


def test_candidate_company_page_urls() -> None:
    """Joining slugs should respect leading slashes and absolute URLs."""

    base = "https://example.com/"
    urls = _candidate_company_page_urls(
        base,
        ["unternehmen", "/presse", "https://external.test/about"],
    )
    assert urls == [
        "https://example.com/unternehmen",
        "https://example.com/presse",
        "https://external.test/about",
    ]


def test_fetch_company_page_tries_candidates(monkeypatch) -> None:
    """Candidate URLs should be fetched in order until one succeeds."""

    calls: list[str] = []

    def fake_extract(url: str):
        calls.append(url)
        if url.endswith("ueber-uns"):
            return build_plain_text_document("Über uns", source=url)
        raise ValueError("missing")

    monkeypatch.setattr("wizard.extract_text_from_url", fake_extract)

    result = _fetch_company_page(
        "https://example.com/",
        ["unternehmen", "ueber-uns"],
    )

    assert result == ("https://example.com/ueber-uns", "Über uns")
    assert calls == [
        "https://example.com/unternehmen",
        "https://example.com/ueber-uns",
    ]


def test_load_company_page_section_updates_state(monkeypatch) -> None:
    """Fetching and summarising a section should store the result."""

    st.session_state.clear()
    st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES] = {}
    st.session_state[StateKeys.COMPANY_PAGE_BASE] = ""
    st.session_state[StateKeys.COMPANY_PAGE_TEXT_CACHE] = {}
    st.session_state["lang"] = "de"

    monkeypatch.setattr(
        "wizard.extract_text_from_url",
        lambda url: build_plain_text_document("Inhalt", source=url),
    )
    monkeypatch.setattr(
        "wizard.summarize_company_page",
        lambda text, label, lang="de": f"{label} :: {lang}",
    )
    monkeypatch.setattr("wizard.st.spinner", lambda *_, **__: contextlib.nullcontext())
    monkeypatch.setattr("wizard.st.info", lambda *_, **__: None)
    monkeypatch.setattr("wizard.st.warning", lambda *_, **__: None)
    monkeypatch.setattr("wizard.st.success", lambda *_, **__: None)

    _load_company_page_section(
        section_key="about",
        base_url="https://example.com/",
        slugs=["unternehmen"],
        label="Über uns",
    )

    stored = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]["about"]
    assert stored["url"].endswith("unternehmen")
    assert stored["summary"] == "Über uns :: de"
    assert stored["label"] == "Über uns"


def test_store_company_page_section_enriches_about(monkeypatch) -> None:
    """Storing the about section should trigger enrichment once."""

    st.session_state.clear()
    st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES] = {}
    st.session_state[StateKeys.PROFILE] = {"company": {}}

    monkeypatch.setattr(
        "wizard._cached_summarize_company_page",
        lambda *_, **__: "Kurzfassung",
    )

    calls: list[dict[str, str | None]] = []

    def fake_enrich(*_, **kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("wizard._enrich_company_profile_from_about", fake_enrich)

    section = cast(
        _CompanySectionConfig,
        {"key": "about", "label": "Über uns", "slugs": ["unternehmen"]},
    )
    _store_company_page_section(
        section=section,
        url="https://example.com/unternehmen",
        text="Wir beschäftigen 120 Mitarbeitende.",
        lang="de",
    )

    stored = st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES]["about"]
    assert stored["summary"] == "Kurzfassung"
    assert calls and calls[0]["section_label"] == "Über uns"


def test_extract_company_size_detects_employee_count() -> None:
    """The size extractor should capture employee count statements."""

    text = "Die Rheinbahn beschäftigt rund 3.370 Menschen und bewegt Düsseldorf."
    assert _extract_company_size(text) == "3370"


def test_enrich_company_profile_from_about_updates_missing_fields(monkeypatch) -> None:
    """About page enrichment should fill empty company fields."""

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = {
        "company": {
            "name": "",
            "hq_location": "",
            "mission": "",
            "size": "",
        }
    }

    monkeypatch.setattr(
        "wizard.extract_company_info",
        lambda text: {
            "name": "Rheinbahn AG",
            "location": "Düsseldorf",
            "mission": "Mobilität für alle",
        },
    )

    about_text = "Die Rheinbahn AG bewegt Düsseldorf und beschäftigt rund 3.370 Menschen, die täglich unterwegs sind."
    _enrich_company_profile_from_about(about_text)

    company = st.session_state[StateKeys.PROFILE]["company"]
    assert company["name"] == "Rheinbahn AG"
    assert company["hq_location"] == "Düsseldorf"
    assert company["mission"] == "Mobilität für alle"
    assert company["size"] == "3370"
    metadata = st.session_state[StateKeys.PROFILE_METADATA]
    name_meta = metadata["rules"]["company.name"]
    assert name_meta["source_kind"] == "company_page"
    assert "company.name" in metadata["llm_fields"]


def test_enrich_company_profile_respects_existing_values(monkeypatch) -> None:
    """Existing user input should not be overwritten by enrichment."""

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = {
        "company": {
            "name": "Vorhanden GmbH",
            "hq_location": "Berlin",
            "mission": "Bestehende Mission",
            "size": "200 Mitarbeitende",
        }
    }

    monkeypatch.setattr(
        "wizard.extract_company_info",
        lambda text: {
            "name": "Neuer Name",
            "location": "München",
            "mission": "Neue Mission",
        },
    )

    _enrich_company_profile_from_about("Wir beschäftigen 500 Mitarbeitende.")

    company = st.session_state[StateKeys.PROFILE]["company"]
    assert company["name"] == "Vorhanden GmbH"
    assert company["hq_location"] == "Berlin"
    assert company["mission"] == "Bestehende Mission"
    assert company["size"] == "200 Mitarbeitende"
    assert StateKeys.PROFILE_METADATA not in st.session_state or not st.session_state[StateKeys.PROFILE_METADATA].get(
        "rules"
    )


def test_enrich_company_profile_via_web_populates_missing(monkeypatch) -> None:
    """Web enrichment should populate missing company details and reuse cache."""

    st.session_state.clear()
    st.session_state[StateKeys.COMPANY_INFO_CACHE] = {}
    st.session_state["lang"] = "en"

    calls: list[str] = []

    def fake_extract(text: str, vector_store_id: str | None = None) -> dict[str, str]:
        calls.append(text)
        return {
            "name": "Acme GmbH",
            "location": "Berlin",
            "mission": "Empower teams",
            "culture": "Inclusive culture",
            "size": "250 employees",
        }

    monkeypatch.setattr("wizard.extract_company_info", fake_extract)

    profile = NeedAnalysisProfile()
    profile.company.name = "Acme GmbH"
    metadata: dict[str, Any] = {}

    _enrich_company_profile_via_web(profile, metadata)

    assert profile.company.hq_location == "Berlin"
    assert profile.company.mission == "Empower teams"
    assert profile.company.culture == "Inclusive culture"
    assert profile.company.size == "250 employees"
    rules = metadata.get("rules", {})
    mission_meta = rules.get("company.mission", {})
    assert mission_meta.get("source_kind") == "web_search"

    profile.company.hq_location = ""
    profile.company.mission = ""
    profile.company.culture = ""
    profile.company.size = ""
    metadata_second: dict[str, Any] = {}

    _enrich_company_profile_via_web(profile, metadata_second)

    assert len(calls) == 1, "Expected cached web enrichment to avoid repeated calls"
    second_rules = metadata_second.get("rules", {})
    assert second_rules.get("company.size", {}).get("value") == "250 employees"


def test_bulk_fetch_company_sections_returns_success_and_miss(monkeypatch) -> None:
    """Bulk fetching should separate successes from misses."""

    def fake_fetch(base_url: str, slugs: Sequence[str]) -> tuple[str, str] | None:
        if "unternehmen" in slugs:
            return (f"{base_url}unternehmen", "Über uns")
        return None

    monkeypatch.setattr("wizard._fetch_company_page", fake_fetch)

    sections = [
        cast(
            _CompanySectionConfig,
            {"key": "about", "label": "Über uns", "slugs": ["unternehmen"]},
        ),
        cast(
            _CompanySectionConfig,
            {"key": "press", "label": "Presse", "slugs": ["presse"]},
        ),
    ]

    successes, misses, errors = _bulk_fetch_company_sections("https://example.com/", sections)

    assert len(successes) == 1
    assert successes[0][0]["key"] == "about"
    assert len(misses) == 1 and misses[0]["key"] == "press"
    assert errors == []


def test_fetch_url_follows_long_redirect_chain(monkeypatch) -> None:
    """Fetching should tolerate long but finite redirect chains."""

    from ingest import extractors

    redirects = [f"https://example.com/hop-{i}" for i in range(7)]
    final_text = "<html>done</html>"
    calls: list[str] = []

    class RedirectResponse:
        def __init__(self, location: str) -> None:
            self.status_code = 302
            self.headers = {"Location": location}

    class SuccessResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, *_, **__):
        calls.append(url)
        if len(calls) <= len(redirects):
            response = RedirectResponse(location=redirects[len(calls) - 1])
            raise requests.HTTPError(response=response)
        return SuccessResponse(final_text)

    monkeypatch.setattr("ingest.extractors.requests.get", fake_get)

    result = extractors._fetch_url("https://example.com/start")

    assert result == final_text
    assert calls == ["https://example.com/start", *redirects]


def test_company_page_helpers_use_cache(monkeypatch) -> None:
    """Repeated lookups should reuse cached fetch, summary and extraction."""

    st.cache_data.clear()
    st.session_state.clear()
    st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES] = {}
    st.session_state[StateKeys.COMPANY_PAGE_BASE] = ""
    st.session_state[StateKeys.COMPANY_PAGE_TEXT_CACHE] = {}
    st.session_state[StateKeys.PROFILE] = {"company": {"name": "", "hq_location": "", "mission": "", "size": ""}}
    st.session_state["lang"] = "de"

    counters = {"fetch": 0, "summary": 0, "extract": 0}

    def fake_extract(url: str):
        counters["fetch"] += 1
        return build_plain_text_document("Inhalt", source=url)

    def fake_summary(text: str, label: str, lang: str = "de") -> str:
        counters["summary"] += 1
        return f"{label}|{lang}"

    def fake_company_info(text: str) -> dict[str, str]:
        counters["extract"] += 1
        return {"name": "Cached GmbH", "location": "Berlin", "mission": "Wir"}

    monkeypatch.setattr("wizard.extract_text_from_url", fake_extract)
    monkeypatch.setattr("wizard.summarize_company_page", fake_summary)
    monkeypatch.setattr("wizard.extract_company_info", fake_company_info)
    monkeypatch.setattr("wizard.st.spinner", lambda *_, **__: contextlib.nullcontext())
    monkeypatch.setattr("wizard.st.info", lambda *_, **__: None)
    monkeypatch.setattr("wizard.st.warning", lambda *_, **__: None)
    monkeypatch.setattr("wizard.st.success", lambda *_, **__: None)

    for _ in range(2):
        _load_company_page_section(
            section_key="about",
            base_url="https://example.com/",
            slugs=["unternehmen"],
            label="Über uns",
        )

    assert counters == {"fetch": 1, "summary": 1, "extract": 1}
