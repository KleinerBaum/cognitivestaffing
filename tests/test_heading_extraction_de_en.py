from ingest.heuristics import apply_basic_fallbacks
from models.need_analysis import NeedAnalysisProfile


def test_german_headings_map_responsibilities_and_requirements() -> None:
    text = (
        "Was dich erwartet:\n"
        "- Du gestaltest datengetriebene Produkte\n"
        "- Gemeinsam mit dem Team entwickelst du neue Modelle\n\n"
        "Darauf freuen wir uns:\n"
        "- Mehrjährige Erfahrung mit Python\n"
        "- Du bringst Wissen in Machine Learning mit\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert any("gestaltest datengetriebene produkte" in item.lower() for item in profile.responsibilities.items)
    requirement_entries = [
        *profile.requirements.hard_skills_required,
        *profile.requirements.soft_skills_required,
        *profile.requirements.tools_and_technologies,
    ]
    assert requirement_entries
    assert any("python" in entry.lower() for entry in requirement_entries)
    assert any("machine learning" in entry.lower() for entry in requirement_entries)


def test_english_headings_map_responsibilities_and_requirements() -> None:
    text = (
        "Your tasks and responsibilities:\n"
        "- Own the data product roadmap\n"
        "- Lead experimentation initiatives\n\n"
        "Must Have Skills:\n"
        "- 5+ years experience in analytics\n"
        "- Expertise in SQL and experimentation methods\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert any("roadmap" in item.lower() for item in profile.responsibilities.items)
    assert any("experimentation" in item.lower() for item in profile.responsibilities.items)

    requirement_entries = [
        *profile.requirements.hard_skills_required,
        *profile.requirements.soft_skills_required,
        *profile.requirements.tools_and_technologies,
    ]
    assert requirement_entries
    assert any("sql" in entry.lower() for entry in requirement_entries)
    assert any("analytics" in entry.lower() for entry in requirement_entries)
