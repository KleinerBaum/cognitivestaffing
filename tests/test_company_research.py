"""Tests for company website research helpers."""

from __future__ import annotations

import contextlib

import streamlit as st

from constants.keys import StateKeys
from wizard import (
    _candidate_company_page_urls,
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

    def fake_extract(url: str) -> str:
        calls.append(url)
        if url.endswith("ueber-uns"):
            return "Über uns"
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

    monkeypatch.setattr("wizard.extract_text_from_url", lambda url: "Inhalt")
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
