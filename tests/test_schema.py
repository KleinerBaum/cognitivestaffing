import pytest

from models.need_analysis import NeedAnalysisProfile
from core.schema import (
    LIST_FIELDS,
    RecruitingWizard,
    SourceAttribution,
    coerce_and_fill,
    process_extracted_profile,
)
from core.schema_defaults import default_recruiting_wizard


def test_list_fields_contains_base_lists() -> None:
    base_lists = {
        "responsibilities.items",
        "requirements.hard_skills_required",
        "requirements.hard_skills_optional",
        "requirements.soft_skills_required",
        "requirements.soft_skills_optional",
        "requirements.certifications",
        "requirements.certificates",
        "compensation.benefits",
        "requirements.languages_required",
        "requirements.tools_and_technologies",
    }
    assert base_lists <= LIST_FIELDS


def test_coerce_and_fill_basic() -> None:
    data = {
        "company": {"name": "Acme"},
        "position": {"job_title": "Engineer", "supervises": 3, "team_size": 10},
        "requirements": {"hard_skills_required": ["Python"]},
        "responsibilities": {"items": ["Code apps"]},
        "employment": {"job_type": "full time", "contract_type": "permanent"},
        "compensation": {
            "benefits": ["Gym", "Gym"],
            "bonus_percentage": 10.0,
            "commission_structure": "10% of sales",
        },
        "meta": {"target_start_date": "2024-01-01"},
    }
    profile = coerce_and_fill(data)
    assert isinstance(profile, NeedAnalysisProfile)
    assert profile.position.job_title == "Engineer"
    assert profile.requirements is not None
    assert profile.responsibilities is not None
    assert profile.employment is not None
    assert profile.compensation is not None
    assert profile.requirements.hard_skills_required == ["Python"]
    assert profile.responsibilities.items == ["Code apps"]
    assert profile.employment.job_type == "full time"
    assert profile.employment.contract_type == "permanent"
    assert profile.team.headcount_current == 3
    assert profile.team.headcount_target == 10
    assert profile.meta.target_start_date == "2024-01-01"
    assert profile.compensation.benefits == ["Gym"]
    assert profile.compensation.bonus_percentage == 10.0
    assert profile.compensation.commission_structure == "10% of sales"
    assert profile.compensation.salary_provided is False
    assert profile.company.name == "Acme"


def test_coerce_and_fill_employment_details() -> None:
    data = {
        "employment": {
            "contract_type": "fixed_term",
            "contract_end": "2025-12-31",
            "work_schedule": "flexitime",
            "remote_percentage": 50,
            "travel_required": True,
            "travel_details": "20% international",
            "relocation_support": True,
            "relocation_details": "Budget provided",
        }
    }
    profile = coerce_and_fill(data)
    assert profile.employment.contract_end == "2025-12-31"
    assert profile.employment.remote_percentage == 50
    assert profile.employment.travel_details == "20% international"
    assert profile.employment.relocation_details == "Budget provided"


def test_coerce_and_fill_alias_mapping() -> None:
    """Alias keys should map to their canonical schema paths."""

    data = {
        "requirements": {"hard_skills": ["Python"]},
        "city": "Berlin",
        "date_of_employment_start": "2024-01-01",
        "hr_contact_name": "Max Mustermann",
        "hr_contact_email": "max@example.com",
        "hr_contact_phone": "+49 30 1234567",
        "hiring_manager_name": "Julia Schmidt",
        "hiring_manager_role": "Head of Engineering",
        "reporting_manager_name": "Petra Müller",
        "employment": {"work_model": "remote"},
        "company": {
            "brand_colour": "#123abc",
            "logo": "https://example.com/logo.svg",
            "tagline": "Einfach. Immer. Da.",
        },
        "position": {
            "department": "Technology",
            "team_structure": "Platform",  # legacy key should feed team.name
            "reporting_line": "VP Engineering",
            "team_size": 12,
            "supervises": 4,
        },
    }
    profile = coerce_and_fill(data)
    assert profile.requirements.hard_skills_required == ["Python"]
    assert profile.location.primary_city == "Berlin"
    assert profile.meta.target_start_date == "2024-01-01"
    assert profile.company.contact_name == "Max Mustermann"
    assert profile.company.contact_email == "max@example.com"
    assert profile.company.contact_phone == "+49 30 1234567"
    assert profile.employment.work_policy == "remote"
    assert profile.process.hiring_manager_name == "Julia Schmidt"
    assert profile.process.hiring_manager_role == "Head of Engineering"
    assert profile.position.reporting_manager_name == "Petra Müller"
    assert profile.company.brand_color == "#123ABC"
    assert str(profile.company.logo_url) == "https://example.com/logo.svg"
    assert profile.company.claim == "Einfach. Immer. Da."
    assert profile.department.name == "Technology"
    assert profile.team.name == "Platform"
    assert profile.team.reporting_line == "VP Engineering"
    assert profile.team.headcount_target == 12
    assert profile.team.headcount_current == 4


def test_coerce_and_fill_alias_mapping_case_insensitive() -> None:
    profile = coerce_and_fill({"Brand Name": "Acme", "CITY": "Hamburg"})
    assert profile.company.brand_name == "Acme"
    assert profile.location.primary_city == "Hamburg"


def test_coerce_and_fill_treats_empty_logo_url_as_none() -> None:
    profile = coerce_and_fill({"company": {"logo_url": ""}})
    assert profile.company.logo_url is None


def test_coerce_and_fill_coerces_scalar_types() -> None:
    data = {
        "requirements": {"hard_skills_required": "Python, SQL"},
        "employment": {"travel_required": "yes", "remote_percentage": "50%"},
        "compensation": {"equity_offered": "false"},
    }
    profile = coerce_and_fill(data)
    assert profile.requirements.hard_skills_required == ["Python", "SQL"]
    assert profile.employment.travel_required is True
    assert profile.employment.remote_percentage == 50
    assert profile.compensation.equity_offered is False


def test_coerce_and_fill_repair_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_repair(payload, *, errors=None):  # type: ignore[unused-ignore]
        calls["payload"] = payload
        calls["errors"] = errors
        return {"company": {"logo": "https://example.com/fixed-logo.png"}}

    monkeypatch.setattr("core.schema.repair_profile_payload", fake_repair)

    profile = coerce_and_fill({"company": {"logo_url": "not-a-url"}})

    assert str(profile.company.logo_url) == "https://example.com/fixed-logo.png"
    assert calls["payload"] == {"company": {"logo_url": "not-a-url"}}
    assert isinstance(calls["errors"], list)


def test_default_insertion() -> None:
    profile = coerce_and_fill({})
    assert profile.position.job_title is None
    assert profile.company.name is None
    assert profile.requirements.hard_skills_required == []


def test_process_extracted_profile_handles_missing_company_name() -> None:
    """Profiles without a company name should be normalized safely."""

    raw_profile = {
        "company": {},
        "position": {"job_title": "Engineer"},
        "requirements": {"hard_skills_required": ["Python"]},
    }

    profile = process_extracted_profile(raw_profile)

    dumped = profile.model_dump()
    assert dumped["company"]["name"] in (None, "")
    assert dumped["position"]["job_title"] == "Engineer"


def test_job_type_invalid() -> None:
    profile = coerce_and_fill({"employment": {"job_type": "unknown"}})
    assert profile.employment is not None
    assert profile.employment.job_type == "unknown"


def test_salary_provided_defaults_to_false_when_missing_or_null() -> None:
    missing_payload = {"compensation": {"salary_max": 100000}}
    profile_missing = coerce_and_fill(missing_payload)
    assert profile_missing.compensation.salary_provided is False

    null_payload = {"compensation": {"salary_provided": None}}
    profile_null = coerce_and_fill(null_payload)
    assert profile_null.compensation.salary_provided is False


def test_schema_roundtrip() -> None:
    """The RecruitingWizard schema should survive JSON roundtrips."""

    payload = default_recruiting_wizard()
    dumped = payload.model_dump(mode="json")
    reloaded = RecruitingWizard.model_validate(dumped)
    assert reloaded == payload
    assert set(dumped["sources"].keys()) == set(payload.sources.root.keys())


def test_default_wizard_marks_required_fields() -> None:
    payload = default_recruiting_wizard()
    assert payload.company.name is None
    assert payload.role.title is None
    assert payload.summary.headline is None

    required_missing = payload.missing_fields.root
    assert {"company.name", "role.title", "summary.headline"} <= set(required_missing)
    for key in ("company.name", "role.title", "summary.headline"):
        entry = required_missing[key]
        assert entry.required is True
        assert entry.reason


def test_source_attribution_accepts_blank_urls() -> None:
    attribution = SourceAttribution(source_url="   ")
    assert attribution.source_url is None
