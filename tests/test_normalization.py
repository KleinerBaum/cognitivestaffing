"""Tests for the normalisation utilities."""

from models.need_analysis import NeedAnalysisProfile
from utils.normalization import (
    normalize_city_name,
    normalize_company_size,
    normalize_country,
    normalize_language,
    normalize_language_list,
    normalize_profile,
)


def test_normalize_country_handles_german_inputs() -> None:
    assert normalize_country("Deutschland") == "Germany"
    assert normalize_country("DE") == "Germany"


def test_normalize_language_handles_german_variants() -> None:
    assert normalize_language("Deutsch") == "German"
    assert normalize_language("de") == "German"
    assert normalize_language_list(["Deutsch", "english", "GERMAN"]) == [
        "German",
        "English",
    ]


def test_normalize_city_name_strips_prefix_and_suffix() -> None:
    assert normalize_city_name("in Düsseldorf eine") == "Düsseldorf"
    assert normalize_city_name("bei Berlin, remote möglich") == "Berlin"


def test_normalize_company_size_parses_numbers() -> None:
    assert normalize_company_size("rund 3.370 Menschen") == "3370"
    assert normalize_company_size("mehr als 500 Mitarbeiter") == "500+"
    assert normalize_company_size("501 – 1000 Mitarbeitende") == "501-1000"


def test_normalize_profile_applies_string_rules() -> None:
    profile = NeedAnalysisProfile.model_validate(
        {
            "company": {
                "logo_url": " https://example.com/logo.svg ",
                "brand_color": "99cc00",
            },
            "position": {"job_title": "Lead Developer (m/w/d)"},
            "location": {"primary_city": "in Düsseldorf eine"},
            "requirements": {"hard_skills_required": [" Python ", "python", ""]},
            "responsibilities": {"items": ["Build APIs ", "Build APIs"]},
        }
    )

    normalized = normalize_profile(profile)

    assert normalized.position.job_title == "Lead Developer"
    assert normalized.location.primary_city == "Düsseldorf"
    assert str(normalized.company.logo_url) == "https://example.com/logo.svg"
    assert normalized.company.brand_color == "#99CC00"
    assert normalized.requirements.hard_skills_required == ["Python"]
    assert normalized.responsibilities.items == ["Build APIs"]
