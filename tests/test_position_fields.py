"""Tests for position-specific heuristic fields."""

from models.need_analysis import NeedAnalysisProfile
from ingest.heuristics import apply_basic_fallbacks


def test_team_structure_and_reporting_line_extraction() -> None:
    text = (
        "Leitung Digital-Projekten (mit interdisziplinären internen & externen Projekt- & Expertenteams).\n"
        "IT-Leiter: Max Mustermann | max.mustermann@example.com\n"
        "HR Ansprechpartner: Benjamin Erben"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.team_structure == "interdisziplinären internen & externen Projekt- & Expertenteams"
    assert profile.position.reporting_line == "IT-Leiter"
    assert profile.position.reporting_manager_name == "Max Mustermann"


def test_reporting_line_skips_hr_contact() -> None:
    text = "Kontakt: recruiting@example.com\nHR Ansprechpartner: Benjamin Erben | +49 123 456 78"

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.position.team_structure is None
    assert profile.position.reporting_line is None
    assert profile.position.reporting_manager_name is None
