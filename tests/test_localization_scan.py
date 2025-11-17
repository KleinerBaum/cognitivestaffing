"""Regression tests for the localisation scan utility."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_localization


@pytest.fixture(name="known_translations", scope="module")
def known_translations_fixture() -> set[str]:
    """Provide a stable translation set for unit tests."""

    return set()


def test_scan_file_detects_untranslated_literal(tmp_path: Path, known_translations: set[str]) -> None:
    """English strings outside ``tr()`` should be reported."""

    sample = tmp_path / "sample.py"
    sample.write_text(
        """
import streamlit as st


def render() -> None:
    st.write("Hello world from widget!")
""".strip()
    )
    offenses = check_localization.scan_file(sample, known_translations)
    assert offenses, "Expected untranslated string to be flagged"
    assert offenses[0].line == 4


def test_scan_file_ignores_translated_pairs(tmp_path: Path, known_translations: set[str]) -> None:
    """Bilingual tuples and ``tr()`` calls should be skipped."""

    sample = tmp_path / "ok.py"
    sample.write_text(
        """
from utils.i18n import tr

LABEL = ("Hallo", f"Hello there {1}")


def render() -> None:
    st.write(tr("Hallo", "Hello there"))
""".strip()
    )
    offenses = check_localization.scan_file(sample, known_translations)
    assert offenses == []


def test_repository_ui_sources_are_translated() -> None:
    """Default UI directories must remain free of hard-coded English strings."""

    targets = [Path(name) for name in check_localization.DEFAULT_DIRECTORIES]
    offenses = check_localization.scan_paths(targets)
    assert not offenses, "Run scripts/check_localization.py to fix untranslated strings"
