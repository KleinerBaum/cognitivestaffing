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
    jd = coerce_and_fill(data)
    assert isinstance(jd, NeedAnalysisProfile)
    assert jd.position.job_title == "Engineer"
    assert jd.requirements is not None
    assert jd.responsibilities is not None
    assert jd.employment is not None
    assert jd.compensation is not None
    assert jd.requirements.hard_skills_required == ["Python"]
    assert jd.responsibilities.items == ["Code apps"]
    assert jd.employment.job_type == "full time"
    assert jd.employment.contract_type == "permanent"
    assert jd.position.supervises == 3
    assert jd.position.team_size == 10
    assert jd.meta.target_start_date == "2024-01-01"
    assert jd.compensation.benefits == ["Gym", "Gym"]
    assert jd.compensation.bonus_percentage == 10.0
    assert jd.compensation.commission_structure == "10% of sales"
    assert jd.compensation.salary_provided is False
    assert jd.company.name == "Acme"


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
    jd = coerce_and_fill(data)
    assert jd.employment.contract_end == "2025-12-31"
    assert jd.employment.remote_percentage == 50
    assert jd.employment.travel_details == "20% international"
    assert jd.employment.relocation_details == "Budget provided"


def test_coerce_and_fill_alias_mapping() -> None:
    """Alias keys should map to their canonical schema paths."""

    data = {
        "requirements": {"hard_skills": ["Python"]},
        "city": "Berlin",
        "date_of_employment_start": "2024-01-01",
    }
    jd = coerce_and_fill(data)
    assert jd.requirements.hard_skills_required == ["Python"]
    assert jd.location.primary_city == "Berlin"
    assert jd.meta.target_start_date == "2024-01-01"


def test_default_insertion() -> None:
    jd = coerce_and_fill({})
    assert jd.position.job_title is None
    assert jd.company.name is None
    assert jd.requirements.hard_skills_required == []


def test_job_type_invalid() -> None:
    jd = coerce_and_fill({"employment": {"job_type": "unknown"}})
    assert jd.employment is not None
    assert jd.employment.job_type == "unknown"
