from models.need_analysis import NeedAnalysisProfile, Position, Requirements
from utils import build_boolean_search


def test_build_boolean_search() -> None:
    profile = NeedAnalysisProfile(
        position=Position(job_title="Data Scientist"),
        requirements=Requirements(
            hard_skills_required=["Python"],
            soft_skills_required=["Communication"],
            tools_and_technologies=["SQL", "Python"],
        ),
    )
    query = build_boolean_search(profile.model_dump())
    assert query == '("Data Scientist") AND ("Python") AND ("Communication") AND ("SQL")'


def test_build_boolean_search_applies_aliases() -> None:
    payload = {
        "role": {"title": "Operations Lead"},
        "requirements": {"hard_skills": ["Python", "SQL"]},
    }

    query = build_boolean_search(payload)

    assert query == '("Operations Lead") AND ("Python") AND ("SQL")'
