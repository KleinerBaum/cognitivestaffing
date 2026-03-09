from __future__ import annotations

from wizard.metadata import validate_required_fields_by_page
from wizard.validators.registry import REQUIRED_FIELD_VALIDATORS
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
        required_fields=("company.contact_email",),
    )

    errors = validate_required_fields_by_page([page])

    assert any("company.contact_email" in error for error in errors)
    assert any("follow-up prefixes" in error for error in errors)


def test_shared_required_field_validators_include_company_fields() -> None:
    assert "company.contact_email" in REQUIRED_FIELD_VALIDATORS
    assert "location.primary_city" in REQUIRED_FIELD_VALIDATORS
