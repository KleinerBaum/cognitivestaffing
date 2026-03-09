from __future__ import annotations

from core.critical_fields import load_critical_fields as load_shared_critical_fields
from wizard.step_status import (
    compute_step_missing,
    is_step_complete,
    iter_step_missing_fields,
    load_critical_fields,
)
from wizard.validators.registry import REQUIRED_FIELD_VALIDATORS
from wizard_pages.base import WizardPage


def _company_step() -> WizardPage:
    return WizardPage(
        key="company",
        label=("Unternehmensdetails", "Company details"),
        panel_header=("Unternehmensdetails", "Company details"),
        panel_subheader=("Profil, Standort & Kontakte", "Profile, location & contacts"),
        panel_intro_variants=(("Intro DE", "Intro EN"),),
        required_fields=(),
        summary_fields=(),
        allow_skip=False,
    )


def test_load_critical_fields_returns_expected_paths() -> None:
    critical_fields = load_critical_fields()

    assert "business_context.domain" in critical_fields
    assert "position.job_title" in critical_fields


def test_compute_step_missing_returns_required_and_critical() -> None:
    profile = {
        "business_context": {"domain": "FinTech"},
        "company": {
            "name": "Acme",
            "contact_name": "Ada",
            "contact_email": "hi@acme.test",
            "contact_phone": "+491234",
        },
        "department": {"name": "Data Platform"},
        "location": {"primary_city": "Berlin"},
    }
    step_meta = _company_step()

    missing = compute_step_missing(profile, step_meta)

    assert missing.required == []
    assert "location.country" in missing.critical
    assert "location.country" in missing.critical


def test_is_step_complete_requires_required_and_critical_fields() -> None:
    profile = {
        "business_context": {"domain": "FinTech"},
        "company": {
            "name": "Acme",
            "contact_name": "Ada",
            "contact_email": "hi@acme.test",
            "contact_phone": "+491234",
        },
        "department": {"name": "Data Platform"},
        "location": {"primary_city": "Berlin", "country": "DE"},
    }
    step_meta = _company_step()

    assert is_step_complete(profile, step_meta) is True


def test_iter_step_missing_fields_deduplicates_order() -> None:
    missing = compute_step_missing({}, _company_step())

    all_missing = list(iter_step_missing_fields(missing))

    assert all_missing[:2] == ["business_context.domain", "company.name"]


def test_step_status_uses_shared_critical_fields_source() -> None:
    assert load_critical_fields() == load_shared_critical_fields()


def test_validator_registry_exposes_company_required_validators() -> None:
    assert "company.contact_email" in REQUIRED_FIELD_VALIDATORS
    assert "location.primary_city" in REQUIRED_FIELD_VALIDATORS


def test_compute_step_missing_blocks_low_confidence_critical_fields() -> None:
    profile = {
        "business_context": {"domain": "FinTech"},
        "company": {
            "name": "Acme",
            "contact_name": "Ada",
            "contact_email": "hi@acme.test",
            "contact_phone": "+491234",
        },
        "department": {"name": "Data Platform"},
        "location": {"primary_city": "Berlin", "country": "DE"},
        "meta": {
            "field_metadata": {
                "location.country": {
                    "source": "heuristic",
                    "confidence": 0.2,
                    "confirmed": False,
                }
            },
            "llm_recovery": {
                "invalid_json": True,
                "low_confidence_fields": ["location.country"],
            },
        },
    }

    missing = compute_step_missing(profile, _company_step())

    assert "location.country" in missing.low_confidence
    assert "location.country" in missing.blocked_by_confidence
    assert is_step_complete(profile, _company_step()) is False


def test_compute_field_score_marks_json_repaired_and_missing_list() -> None:
    from wizard.step_status import compute_field_score

    profile = {
        "requirements": {"hard_skills_required": []},
        "meta": {
            "llm_recovery": {
                "invalid_json": True,
                "low_confidence_fields": ["requirements.hard_skills_required"],
            }
        },
    }

    score = compute_field_score(profile, "requirements.hard_skills_required", is_critical=True)

    assert score.tier == "low"
    assert "REQ_LIST_MISSING" in score.reasons
    assert "JSON_REPAIRED" in score.reasons
