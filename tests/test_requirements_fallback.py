"""Tests for requirement heuristics fallback."""

from models.need_analysis import NeedAnalysisProfile
from ingest.heuristics import apply_basic_fallbacks


def test_requirements_split_and_languages() -> None:
    text = (
        "Must-haves:\n"
        "- Python & Data Science Erfahrung\n"
        "- Du arbeitest analytisch und strukturiert\n"
        "- AWS ML Specialty certification\n"
        "- Englisch (Team language)\n"
        "\n"
        "Nice-to-haves:\n"
        "- Docker\n"
        "- Kommunikationsstärke\n"
        "- Deutsch nice-to-have\n"
    )
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    r = profile.requirements
    assert "Python & Data Science Erfahrung" in r.hard_skills_required
    assert "Docker" in r.hard_skills_optional
    assert "Du arbeitest analytisch und strukturiert" in r.soft_skills_required
    assert "Kommunikationsstärke" in r.soft_skills_optional
    assert "English" in r.languages_required
    assert "German" in r.languages_optional
    assert any("aws ml specialty" in c.lower() for c in r.certifications)
    tools = {t.lower() for t in r.tools_and_technologies}
    assert "python" in tools and "docker" in tools


def test_requirements_formal_heading_variant() -> None:
    text = (
        "Was Sie mitbringen:\n"
        "• Kommunikationsstärke\n"
        "• Erfahrung im Vertrieb\n"
        "\n"
        "Ihre Aufgaben:\n"
        "• Kunden beraten\n"
    )
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    r = profile.requirements
    assert "Erfahrung im Vertrieb" in r.hard_skills_required
    assert "Kommunikationsstärke" in r.soft_skills_required
    assert profile.responsibilities.items == ["Kunden beraten"]


def test_requirements_new_german_heading_variants() -> None:
    text = (
        "Qualifikationen:\n"
        "- Erfahrung in der Datenanalyse\n"
        "\n"
        "Deine Pluspunkte:\n"
        "- Erfahrung mit Tableau\n"
    )
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    r = profile.requirements
    assert "Erfahrung in der Datenanalyse" in r.hard_skills_required
    assert "Erfahrung mit Tableau" in r.hard_skills_optional


def test_requirements_anforderungsprofil_heading() -> None:
    text = (
        "Anforderungsprofil:\n"
        "- Praxis mit CRM-Systemen\n"
        "\n"
        "Das wäre toll:\n"
        "- Salesforce-Zertifizierung\n"
    )
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    r = profile.requirements
    assert "Praxis mit CRM-Systemen" in r.hard_skills_required
    assert "Salesforce-Zertifizierung" in r.hard_skills_optional
