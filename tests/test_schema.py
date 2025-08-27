from models.need_analysis import NeedAnalysisProfile
from core.schema import coerce_and_fill, LIST_FIELDS


def test_list_fields_contains_base_lists() -> None:
    base_lists = {
        "responsibilities.items",
        "requirements.hard_skills",
        "requirements.soft_skills",
        "requirements.certifications",
        "compensation.benefits",
        "requirements.languages_required",
        "requirements.tools_and_technologies",
    }
    assert base_lists <= LIST_FIELDS


def test_coerce_and_fill_basic() -> None:
    data = {
        "company": {"name": "Acme"},
        "position": {"job_title": "Engineer", "supervises": 3},
        "requirements": {"hard_skills": ["Python"]},
        "responsibilities": {"items": ["Code apps"]},
        "employment": {"job_type": "full time", "contract_type": "permanent"},
        "compensation": {"benefits": ["Gym", "Gym"]},
        "meta": {"target_start_date": "2024-01-01"},
    }
    jd = coerce_and_fill(data)
    assert isinstance(jd, NeedAnalysisProfile)
    assert jd.position.job_title == "Engineer"
    assert jd.requirements is not None
    assert jd.responsibilities is not None
    assert jd.employment is not None
    assert jd.compensation is not None
    assert jd.requirements.hard_skills == ["Python"]
    assert jd.responsibilities.items == ["Code apps"]
    assert jd.employment.job_type == "full time"
    assert jd.employment.contract_type == "permanent"
    assert jd.position.supervises == 3
    assert jd.meta.target_start_date == "2024-01-01"
    assert jd.compensation.benefits == ["Gym", "Gym"]
    assert jd.company.name == "Acme"


def test_default_insertion() -> None:
    jd = coerce_and_fill({})
    assert jd.position.job_title is None
    assert jd.company.name is None
    assert jd.requirements.hard_skills == []


def test_job_type_invalid() -> None:
    jd = coerce_and_fill({"employment": {"job_type": "unknown"}})
    assert jd.employment is not None
    assert jd.employment.job_type == "unknown"
