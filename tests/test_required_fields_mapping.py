from __future__ import annotations

from wizard.metadata import validate_required_fields_by_page
from wizard_pages import WizardPage


def test_required_fields_match_page_ownership() -> None:
    errors = validate_required_fields_by_page()

    assert errors == []


def test_required_fields_detect_prefix_mismatch() -> None:
    page = WizardPage(
        key="team",
        label=("Team", "Team"),
        panel_header=("Team", "Team"),
        panel_subheader=("Team", "Team"),
        panel_intro_variants=tuple(),
        required_fields=("department.name",),
    )

    errors = validate_required_fields_by_page([page])

    assert any("department.name" in error for error in errors)
    assert any("follow-up prefixes" in error for error in errors)
