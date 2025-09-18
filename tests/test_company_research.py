"""Tests for company website research helpers."""

from __future__ import annotations

import contextlib

import streamlit as st

from constants.keys import StateKeys
from ingest.types import build_plain_text_document
from wizard import (
    _candidate_company_page_urls,
    _enrich_company_profile_from_about,
    _extract_company_size,
    _fetch_company_page,
    _load_company_page_section,
    _normalise_company_base_url,
)


def test_normalise_company_base_url() -> None:
    """The company URL normaliser should add missing schema and slashes."""

    assert _normalise_company_base_url("https://example.com") == "https://example.com/"
    assert _normalise_company_base_url("www.example.com") == "https://www.example.com/"
    assert (
        _normalise_company_base_url("https://example.com/de")
        == "https://example.com/de/"
    )
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


def test_extract_company_size_detects_employee_count() -> None:
    """The size extractor should capture employee count statements."""

    text = "Die Rheinbahn beschäftigt rund 3.370 Menschen und bewegt Düsseldorf."
    assert _extract_company_size(text) == "rund 3.370 Menschen"


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

    about_text = (
        "Die Rheinbahn AG bewegt Düsseldorf und beschäftigt rund 3.370 Menschen,"
        " die täglich unterwegs sind."
    )
    _enrich_company_profile_from_about(about_text)

    company = st.session_state[StateKeys.PROFILE]["company"]
    assert company["name"] == "Rheinbahn AG"
    assert company["hq_location"] == "Düsseldorf"
    assert company["mission"] == "Mobilität für alle"
    assert company["size"] == "rund 3.370 Menschen"


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
