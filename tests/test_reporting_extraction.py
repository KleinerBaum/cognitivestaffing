"""Tests for reporting line and direct report extraction heuristics."""

from models.need_analysis import NeedAnalysisProfile
from ingest.heuristics import apply_basic_fallbacks


def test_reports_to_extraction_english() -> None:
    text = "This role reports to the Chief Marketing Officer."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.reports_to == "Chief Marketing Officer"


def test_reports_to_extraction_german() -> None:
    text = "Berichtet an den Leiter der Abteilung Forschung."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.reports_to == "Leiter der Abteilung Forschung"


def test_supervises_from_leading_team() -> None:
    text = "You will lead a team of 4 developers."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.supervises == 4


def test_supervises_from_german_team_phrase() -> None:
    text = "Leitest ein Team von 10 Mitarbeitern."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.supervises == 10


def test_supervises_ignores_non_lead_team_size() -> None:
    text = "You will work in a team of 8 people collaborating closely."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.supervises is None
