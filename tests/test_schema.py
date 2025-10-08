from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill, LIST_FIELDS


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
    assert profile.position.supervises == 3
    assert profile.position.team_size == 10
    assert profile.meta.target_start_date == "2024-01-01"
    assert profile.compensation.benefits == ["Gym", "Gym"]
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
    }
    profile = coerce_and_fill(data)
    assert profile.requirements.hard_skills_required == ["Python"]
    assert profile.location.primary_city == "Berlin"
    assert profile.meta.target_start_date == "2024-01-01"


def test_default_insertion() -> None:
    profile = coerce_and_fill({})
    assert profile.position.job_title is None
    assert profile.company.name is None
    assert profile.requirements.hard_skills_required == []


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
