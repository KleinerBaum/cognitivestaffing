from __future__ import annotations

from collections.abc import Mapping

from constants.keys import StateKeys
from wizard.validation import resolve_missing_required_fields
from wizard_pages.base import WizardPage


def _resolver(data: Mapping[str, object], path: str, default: object | None) -> object | None:
    cursor: object = data
    for part in path.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return default
    return cursor


def test_resolve_missing_required_fields_merges_validator_errors() -> None:
    page = WizardPage(
        key="company",
        label=("Company", "Company"),
        panel_header=("Company", "Company"),
        panel_subheader=("Company", "Company"),
        panel_intro_variants=tuple(),
        required_fields=("company.contact_email",),
    )

    def _validator(_value: str | None) -> tuple[str | None, tuple[str, str] | None]:
        return None, ("Ungültig", "Invalid")

    missing, errors = resolve_missing_required_fields(
        page,
        required_field_validators={"company.contact_email": _validator},
        validated_fields=set(),
        value_resolver=_resolver,
        session_state={StateKeys.PROFILE: {"company": {"contact_email": "foo"}}},
    )

    assert missing == ["company.contact_email"]
    assert "company.contact_email" in errors


def test_resolve_missing_required_fields_uses_widget_value_for_validated_fields() -> None:
    page = WizardPage(
        key="company",
        label=("Company", "Company"),
        panel_header=("Company", "Company"),
        panel_subheader=("Company", "Company"),
        panel_intro_variants=tuple(),
        required_fields=("company.contact_email",),
    )

    missing, errors = resolve_missing_required_fields(
        page,
        required_field_validators={},
        validated_fields={"company.contact_email"},
        value_resolver=_resolver,
        session_state={
            StateKeys.PROFILE: {"company": {"contact_email": "from-profile@example.com"}},
            "company.contact_email": "from-widget@example.com",
        },
    )

    assert missing == []
    assert errors == {}
