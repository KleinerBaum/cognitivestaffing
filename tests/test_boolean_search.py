from models.need_analysis import NeedAnalysisProfile, Position, Requirements
from utils import build_boolean_search


def test_build_boolean_search() -> None:
    profile = NeedAnalysisProfile(
        position=Position(job_title="Data Scientist"),
        requirements=Requirements(
            hard_skills=["Python"],
            soft_skills=["Communication"],
            tools_and_technologies=["SQL", "Python"],
        ),
    )
    query = build_boolean_search(profile.model_dump())
    assert query == '("Data Scientist") AND ("Python" OR "Communication" OR "SQL")'
