from core.schema import (
    LIST_FIELDS,
    VacalyserJD,
    coerce_and_fill,
)


def test_constants() -> None:
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


def test_coerce_and_fill_partial_and_aliases() -> None:
    data = {
        "position": {"job_title": " Engineer "},
        "requirements": {"hard_skills": "Python"},
        "contract_type": "full-time",
        "tasks": "Code apps",
        "compensation": {"benefits": ["Gym", "", "Gym"]},
    }
    jd = coerce_and_fill(data)
    assert isinstance(jd, VacalyserJD)
    assert jd.position.job_title == "Engineer"
    assert jd.requirements.hard_skills == ["Python"]
    assert jd.employment.job_type == "Full-time"
    assert jd.responsibilities.items == ["Code apps"]
    assert jd.compensation.benefits == ["Gym"]
    assert jd.company.name == ""


def test_default_insertion() -> None:
    jd = coerce_and_fill({})
    assert jd.position.job_title == ""
    assert jd.requirements.hard_skills == []


def test_alias_priority() -> None:
    data = {"job_title": "Old", "position": {"job_title": "New"}}
    jd = coerce_and_fill(data)
    assert jd.position.job_title == "New"


def test_tasks_merge_without_duplicates() -> None:
    jd = coerce_and_fill(
        {
            "responsibilities": {"items": ["Task A"]},
            "tasks": "Task B",
        }
    )
    assert jd.responsibilities.items == ["Task A", "Task B"]

    jd2 = coerce_and_fill(
        {
            "responsibilities": {"items": ["Task A"]},
            "tasks": "Task A",
        }
    )
    assert jd2.responsibilities.items == ["Task A"]


def test_remote_policy_alias_priority() -> None:
    jd = coerce_and_fill(
        {
            "employment": {"work_policy": "Hybrid"},
            "remote_policy": "Fully remote",
        }
    )
    assert jd.employment.work_policy == "Hybrid"
    assert "remote_policy" not in jd.model_dump(mode="json")


def test_list_coercion_split_and_dedupe() -> None:
    jd = coerce_and_fill({"requirements": {"hard_skills": "Python, Java\nPython"}})
    assert jd.requirements.hard_skills == ["Python", "Java"]


def test_coerce_flat_aliases() -> None:
    data = {"job_title": "Dev", "company_name": "Acme", "location": "Berlin"}
    jd = coerce_and_fill(data)
    assert jd.position.job_title == "Dev"
    assert jd.company.name == "Acme"
    assert jd.location.primary_city == "Berlin"


def test_cross_field_dedupe() -> None:
    data = {
        "remote_policy": "Fully remote",
        "responsibilities": {"items": ["Develop APIs", "Fully remote"]},
    }
    jd = coerce_and_fill(data)
    assert jd.employment.work_policy == "Fully remote"
    assert jd.responsibilities.items == ["Develop APIs"]


def test_job_type_normalization() -> None:
    jd = coerce_and_fill({"employment": {"job_type": "full time"}})
    assert jd.employment.job_type == "Full-time"


def test_job_type_invalid() -> None:
    jd = coerce_and_fill({"employment": {"job_type": "unknown"}})
    assert jd.employment.job_type == "unknown"
