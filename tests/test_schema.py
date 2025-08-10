from core.schema import ALL_FIELDS, LIST_FIELDS, VacalyserJD, coerce_and_fill


def test_constants() -> None:
    assert len(ALL_FIELDS) == 23
    assert LIST_FIELDS == {
        "responsibilities",
        "hard_skills",
        "soft_skills",
        "certifications",
        "benefits",
        "languages_required",
        "tools_and_technologies",
    }


def test_coerce_and_fill_partial_and_aliases() -> None:
    data = {
        "job_title": " Engineer ",
        "hard_skills": "Python",
        "requirements": "BSc",
        "contract_type": "full-time",
        "tasks": "Code apps",
        "benefits": ["Gym", "", "Gym"],
    }
    jd = coerce_and_fill(data)
    assert isinstance(jd, VacalyserJD)
    assert jd.job_title == "Engineer"
    assert jd.hard_skills == ["Python"]
    assert jd.qualifications == "BSc"
    assert jd.job_type == "full-time"
    assert jd.responsibilities == ["Code apps"]
    assert jd.benefits == ["Gym"]
    # missing field filled with default
    assert jd.company_name == ""
