"""Tests for country and language normalisation utilities."""

from utils.normalization import (
    normalize_country,
    normalize_language,
    normalize_language_list,
)


def test_normalize_country_handles_german_inputs() -> None:
    assert normalize_country("Deutschland") == "Germany"
    assert normalize_country("DE") == "Germany"


def test_normalize_language_handles_german_variants() -> None:
    assert normalize_language("Deutsch") == "German"
    assert normalize_language("de") == "German"
    assert normalize_language_list(["Deutsch", "english", "GERMAN"]) == [
        "German",
        "English",
    ]
