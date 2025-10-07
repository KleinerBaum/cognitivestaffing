"""Unit tests for the rule-based extraction helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rules import apply_rules, matches_to_patch, build_rule_metadata  # noqa: E402
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


def test_apply_rules_handles_table_layout() -> None:
    """Table rows should map to profile fields via layout heuristics."""

    table_block = ContentBlock(
        type="table",
        text="Location | Munich, Germany\nEmail | hiring@example.de",
        metadata={
            "rows": [["Location", "Munich, Germany"], ["Email", "hiring@example.de"]]
        },
    )
    matches = apply_rules([table_block])
    assert matches["location.primary_city"].value == "Munich"
    assert matches["location.primary_city"].rule == "layout.table"
    assert matches["location.country"].value == "Germany"
    assert matches["company.contact_email"].value == "hiring@example.de"


def test_apply_rules_handles_land_table_keyword() -> None:
    """Table headers labelled Land should map to the country field."""

    table_block = ContentBlock(
        type="table",
        text="Land | Deutschland",
        metadata={"rows": [["Land", "Deutschland"]]},
    )
    matches = apply_rules([table_block])
    assert matches["location.country"].value == "Deutschland"


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
    assert matches["location.country"].value == "Germany"


def test_regex_matches_land_prefix_for_country() -> None:
    """Inline Land: prefixes should populate the country field."""

    text_block = ContentBlock(type="paragraph", text="Land: Deutschland")
    matches = apply_rules([text_block])
    assert matches["location.country"].value == "Deutschland"
    assert "location.primary_city" not in matches
