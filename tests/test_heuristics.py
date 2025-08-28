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
    jd = parse_extraction('{"position": {"job_title": "Dev"}, "city": "Düsseldorf"}')
    assert jd.location.primary_city == "Düsseldorf"


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
