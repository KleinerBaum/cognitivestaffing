from ingest.heuristics import (
    apply_basic_fallbacks,
    guess_city,
    guess_company,
    guess_job_title,
)
from models.need_analysis import NeedAnalysisProfile
from utils.json_parse import parse_extraction


def test_guess_job_title_strip_gender() -> None:
    text = "Senior Data Scientist (m/w/d) – RAG, OpenAI & Recruiting Tech"
    assert guess_job_title(text) == "Senior Data Scientist"


def test_guess_company_brand() -> None:
    text = "Wir sind Vacalyser, ein Tech-Brand der Example GmbH"
    name, brand = guess_company(text)
    assert name == "Example GmbH"
    assert brand == "Vacalyser"


def test_guess_city_from_header() -> None:
    text = "Berlin | Hybrid | ab 01.10.2024"
    assert guess_city(text) == "Berlin"


def test_parse_extraction_city_alias() -> None:
    profile = parse_extraction(
        '{"position": {"job_title": "Dev"}, "city": "Düsseldorf"}'
    )
    assert profile.location.primary_city == "Düsseldorf"


def test_employment_and_start_date_fallbacks() -> None:
    text = (
        "Festanstellung | Vollzeit\n"
        "Hybrid (2-3 Tage/Woche im Office)\n"
        "Start ab 01.10.2024"
    )
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.job_type == "full_time"
    assert profile.employment.contract_type == "permanent"
    assert profile.employment.work_policy == "hybrid"
    assert profile.employment.remote_percentage == 50
    assert profile.meta.target_start_date == "2024-10-01"


def test_compensation_fallbacks() -> None:
    text = "💰 Gehalt: 65.000–85.000 € + 10% Variable + Bonus quartalsweise"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.compensation.salary_min == 65000.0
    assert profile.compensation.salary_max == 85000.0
    assert profile.compensation.currency == "EUR"
    assert profile.compensation.variable_pay is True
    assert profile.compensation.bonus_percentage == 10.0
    assert profile.compensation.commission_structure
    assert profile.compensation.commission_structure.lower().startswith("bonus")


def test_responsibility_fallbacks() -> None:
    text = (
        "Dein Spielfeld:\n"
        "- Features entwickeln\n"
        "- Team unterstützen\n\n"
        "Was du mitbringst:\n"
        "- Python Erfahrung\n"
    )
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.responsibilities.items == [
        "Features entwickeln",
        "Team unterstützen",
    ]
    assert profile.position.role_summary == "Features entwickeln"


def test_responsibility_heading_variants() -> None:
    text = (
        "Was dich erwartet:\n"
        "• Kunden beraten\n"
        "• Angebote erstellen\n"
        "Dein Profil:\n"
        "• Kommunikationsstärke\n"
    )
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.responsibilities.items == [
        "Kunden beraten",
        "Angebote erstellen",
    ]
