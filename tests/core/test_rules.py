"""Unit tests for the rule-based extraction helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.confidence import ConfidenceTier  # noqa: E402
from core.rules import (  # noqa: E402
    _extract_location,
    apply_rules,
    build_rule_metadata,
    matches_to_patch,
)
from ingest.types import ContentBlock  # noqa: E402


def test_apply_rules_detects_email_and_salary() -> None:
    """Emails and salary spans should be extracted from plain text blocks."""

    blocks = [
        ContentBlock(type="paragraph", text="Kontakt: hr@example.com"),
        ContentBlock(type="paragraph", text="Salary: €50.000 - €70.000 gross"),
    ]
    matches = apply_rules(blocks)
    assert matches["company.contact_email"].value == "hr@example.com"
    assert matches["compensation.salary_min"].value == 50000.0
    assert matches["compensation.salary_max"].value == 70000.0
    assert matches["compensation.currency"].value == "EUR"
    assert matches["compensation.salary_provided"].value is True

    patch = matches_to_patch(matches)
    assert patch["company"]["contact_email"] == "hr@example.com"
    assert patch["compensation"]["salary_min"] == 50000.0

    metadata = build_rule_metadata(matches)
    assert "company.contact_email" in metadata["locked_fields"]
    rule_meta = metadata["rules"]["company.contact_email"]
    assert rule_meta["locked"] is True
    assert rule_meta["confidence"] >= 0.9
    confidence_meta = metadata["field_confidence"]["company.contact_email"]
    assert confidence_meta["tier"] == ConfidenceTier.RULE_STRONG.value
    assert confidence_meta["source"] == "rule"
    assert confidence_meta["score"] == pytest.approx(matches["company.contact_email"].confidence)


def test_apply_rules_handles_table_layout() -> None:
    """Table rows should map to profile fields via layout heuristics."""

    table_block = ContentBlock(
        type="table",
        text="Location | Munich, Germany\nEmail | hiring@example.de",
        metadata={"rows": [["Location", "Munich, Germany"], ["Email", "hiring@example.de"]]},
    )
    matches = apply_rules([table_block])
    assert matches["location.primary_city"].value == "Munich"
    assert matches["location.primary_city"].rule == "layout.table"
    assert matches["location.country"].value == "DE"
    assert matches["company.contact_email"].value == "hiring@example.de"


def test_apply_rules_handles_land_table_keyword() -> None:
    """Table headers labelled Land should map to the country field."""

    table_block = ContentBlock(
        type="table",
        text="Land | Deutschland",
        metadata={"rows": [["Land", "Deutschland"]]},
    )
    matches = apply_rules([table_block])
    assert matches["location.country"].value == "DE"


def test_regex_prioritised_over_layout_conflict() -> None:
    """Regex matches should outrank layout-based findings when conflicting."""

    table_block = ContentBlock(
        type="table",
        text="Location | Munich",
        metadata={"rows": [["Location", "Munich"]]},
    )
    text_block = ContentBlock(type="paragraph", text="Location: Berlin, Germany")
    matches = apply_rules([table_block, text_block])
    assert matches["location.primary_city"].value == "Berlin"
    assert matches["location.primary_city"].rule == "regex.location"
    assert matches["location.country"].value == "DE"


def test_regex_matches_land_prefix_for_country() -> None:
    """Inline Land: prefixes should populate the country field."""

    text_block = ContentBlock(type="paragraph", text="Land: Deutschland")
    matches = apply_rules([text_block])
    assert matches["location.country"].value == "DE"
    assert "location.primary_city" not in matches


def test_regex_matches_land_prefix_with_city_value() -> None:
    """Inline Land: prefixes with city tokens should populate the city field."""

    text_block = ContentBlock(type="paragraph", text="Land: Düsseldorf")
    matches = apply_rules([text_block])
    assert matches["location.primary_city"].value == "Düsseldorf"
    assert matches["location.country"].value == "DE"


def test_extract_location_returns_city_and_country() -> None:
    """City and country should be parsed from inline statements."""

    city, country = _extract_location("Location: Munich, Germany")
    assert city == "Munich"
    assert country == "DE"


def test_extract_location_infers_country_from_city() -> None:
    """City-only lines should infer the ISO country when known."""

    city, country = _extract_location("Location: Berlin")
    assert city == "Berlin"
    assert country == "DE"


def test_extract_location_rejects_disqualifying_lines() -> None:
    """Digits, URLs, and emails should prevent extracting a city value."""

    disqualifying_inputs = [
        "Location: 80331 Munich",
        "Location: http://example.com/offices",
        "Location: contact@example.com",
    ]
    for text in disqualifying_inputs:
        city, country = _extract_location(text)
        assert city is None
        assert country is None


def test_extract_location_ignores_remote_keyword() -> None:
    """Non-location keywords after Standort should be ignored."""

    city, country = _extract_location("Standort: Remote")
    assert city is None
    assert country is None

    city, country = _extract_location("Standort: Berlin")
    assert city == "Berlin"
    assert country == "DE"

    city, country = _extract_location("Land: Düsseldorf")
    assert city == "Düsseldorf"
    assert country == "DE"


def test_extract_location_supports_parentheses_and_bullets() -> None:
    """Lowercase and bullet-separated pairs should populate city and country."""

    city, country = _extract_location("location: berlin (germany)")
    assert city == "berlin"
    assert country == "DE"

    city, country = _extract_location("Standort: Berlin • Germany")
    assert city == "Berlin"
    assert country == "DE"


def test_extract_location_handles_dash_separated_values() -> None:
    """En dash-separated values should populate both fields."""

    city, country = _extract_location("Hauptstandort: Wien – Österreich")
    assert city == "Wien"
    assert country == "AT"


def test_apply_rules_handles_einsatzort_and_branche_table_keywords() -> None:
    """Einsatzort and Branche table headers should populate city and industry."""

    table_block = ContentBlock(
        type="table",
        text="Einsatzort | Berlin, Deutschland\nBranche | IT-Dienstleistungen",
        metadata={
            "rows": [
                ["Einsatzort", "Berlin, Deutschland"],
                ["Branche", "IT-Dienstleistungen"],
            ]
        },
    )
    matches = apply_rules([table_block])
    assert matches["location.primary_city"].value == "Berlin"
    assert matches["location.country"].value == "DE"
    assert matches["company.industry"].value == "IT-Dienstleistungen"


def test_apply_rules_handles_land_header_with_city_value() -> None:
    """Land table headers with city values should fill the city field."""

    table_block = ContentBlock(
        type="table",
        text="Land | Düsseldorf",
        metadata={"rows": [["Land", "Düsseldorf"]]},
    )
    matches = apply_rules([table_block])
    assert matches["location.primary_city"].value == "Düsseldorf"
    assert matches["location.country"].value == "DE"


def test_apply_rules_handles_inline_einsatzort_and_branche() -> None:
    """Inline Einsatzort and Branche lines should map to location and industry fields."""

    blocks = [
        ContentBlock(type="paragraph", text="Einsatzort: Hamburg"),
        ContentBlock(type="paragraph", text="Branche: Erneuerbare Energien"),
        ContentBlock(type="paragraph", text="Weitere Informationen folgen."),
    ]
    matches = apply_rules(blocks)
    assert matches["location.primary_city"].value == "Hamburg"
    assert matches["location.country"].value == "DE"
    assert matches["company.industry"].value == "Erneuerbare Energien"


def test_apply_rules_ignores_remote_location_value() -> None:
    """Rule-based extraction should skip remote placeholders for city."""

    blocks = [
        ContentBlock(type="paragraph", text="Standort: Remote"),
        ContentBlock(type="paragraph", text="Standort: Berlin"),
    ]
    matches = apply_rules(blocks)
    assert matches["location.primary_city"].value == "Berlin"
    assert matches["location.primary_city"].rule == "regex.location"
    assert "Standort: Remote" not in matches["location.primary_city"].source_text


def test_apply_rules_handles_city_town_prefix_and_trailing_parentheses() -> None:
    """Lowercase City/Town lines with qualifiers should fill the city field."""

    blocks = [ContentBlock(type="paragraph", text="city/town – berlin (remote)")]
    matches = apply_rules(blocks)
    assert matches["location.primary_city"].value == "berlin"
    assert matches["location.country"].value == "DE"


def test_apply_rules_handles_office_prefix_with_hq_suffix() -> None:
    """Office prefixed lines should ignore HQ qualifiers and capture the city."""

    blocks = [ContentBlock(type="paragraph", text="Office – Zürich HQ")]
    matches = apply_rules(blocks)
    assert matches["location.primary_city"].value == "Zürich"
    assert matches["location.country"].value == "CH"
