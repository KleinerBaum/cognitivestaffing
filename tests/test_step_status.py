from __future__ import annotations

from wizard.step_status import (
    compute_step_missing,
    is_step_complete,
    iter_step_missing_fields,
    load_critical_fields,
)
from wizard_pages.base import WizardPage


def _company_step() -> WizardPage:
    return WizardPage(
        key="company",
        label=("Unternehmen", "Company"),
        panel_header=("Unternehmen", "Company"),
        panel_subheader=("Profil & Kontakt", "Profile & contact"),
        panel_intro_variants=(("Intro DE", "Intro EN"),),
        required_fields=("company.name", "company.contact_email", "location.primary_city"),
        summary_fields=(),
        allow_skip=False,
    )


def test_load_critical_fields_returns_expected_paths() -> None:
    critical_fields = load_critical_fields()

    assert "company.name" in critical_fields
    assert "position.job_title" in critical_fields


def test_compute_step_missing_returns_required_and_critical() -> None:
    profile = {
        "company": {"name": "Acme", "contact_email": "hi@acme.test"},
        "location": {"primary_city": "Berlin"},
    }
    step_meta = _company_step()

    missing = compute_step_missing(profile, step_meta)

    assert missing.required == []
    assert "company.contact_phone" in missing.critical
    assert "location.country" in missing.critical


def test_is_step_complete_requires_required_and_critical_fields() -> None:
    profile = {
        "company": {
            "name": "Acme",
            "contact_name": "Ada",
            "contact_email": "hi@acme.test",
            "contact_phone": "+491234",
        },
        "location": {"primary_city": "Berlin", "country": "DE"},
    }
    step_meta = _company_step()

    assert is_step_complete(profile, step_meta) is True


def test_iter_step_missing_fields_deduplicates_order() -> None:
    missing = compute_step_missing({}, _company_step())

    all_missing = list(iter_step_missing_fields(missing))

    assert all_missing[:2] == ["company.name", "company.contact_email"]
