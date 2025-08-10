from core.schema import (
    ALL_FIELDS,
    LIST_FIELDS,
    STRING_FIELDS,
    VacalyserJD,
    coerce_and_fill,
)


def test_constants() -> None:
    assert len(ALL_FIELDS) == 22
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


def test_default_insertion() -> None:
    """All missing fields are populated with default empty values."""

    jd = coerce_and_fill({})
    for field in STRING_FIELDS:
        assert getattr(jd, field) == ""
    for field in LIST_FIELDS:
        assert getattr(jd, field) == []


def test_alias_priority() -> None:
    """Canonical fields are not overridden by aliases."""

    data = {"requirements": "BSc", "qualifications": "MSc"}
    jd = coerce_and_fill(data)
    assert jd.qualifications == "MSc"


def test_list_coercion_split_and_dedupe() -> None:
    """String list fields are split on newlines/commas and deduplicated."""

    jd = coerce_and_fill({"hard_skills": "Python, Java\nPython"})
    assert jd.hard_skills == ["Python", "Java"]
