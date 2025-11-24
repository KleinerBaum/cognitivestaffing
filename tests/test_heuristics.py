import logging
from importlib import import_module

import pytest
import ingest.heuristics as heuristics

from ingest.heuristics import (
    apply_basic_fallbacks,
    _extract_benefits_from_text,
    guess_city,
    guess_company,
    guess_employment_details,
    guess_job_title,
)
from openai_utils.extraction import _prepare_job_ad_payload
from models.need_analysis import NeedAnalysisProfile
from utils.json_parse import parse_extraction


def _has_spacy_pipeline() -> bool:
    try:
        module = import_module("spacy")
    except ModuleNotFoundError:
        return False
    try:
        module.load("de_core_news_sm")
    except OSError:
        return False
    except Exception:
        return False
    return True


HAS_SPACY_PIPELINE = _has_spacy_pipeline()


def test_guess_job_title_retains_gender_suffix() -> None:
    text = "Senior Data Scientist (m/w/d) – RAG, OpenAI & Recruiting Tech"
    assert guess_job_title(text) == "Senior Data Scientist (m/w/d)"


def test_guess_job_title_multiline_gender_suffix() -> None:
    text = "Senior Data Scientist (m/w/d)\n– RAG, OpenAI & Recruiting Tech"
    assert guess_job_title(text) == "Senior Data Scientist (m/w/d) – RAG, OpenAI & Recruiting Tech"


def test_guess_job_title_skips_location_banner() -> None:
    text = "Berlin | Germany\nSenior Data Scientist (m/w/d)"
    assert guess_job_title(text) == "Senior Data Scientist (m/w/d)"


def test_guess_job_title_skips_known_company_banner() -> None:
    text = "Cognitive Needs GmbH\nSenior Data Scientist (m/w/d)"
    assert guess_job_title(text, skip_phrases=["Cognitive Needs GmbH"]) == "Senior Data Scientist (m/w/d)"


def test_prepare_job_ad_payload_adds_gender_marker_for_german_heading() -> None:
    session_data = {
        "lang": "de",
        "position": {"job_title": "Data Scientist"},
        "company": {"name": "Example GmbH"},
    }
    payload, document = _prepare_job_ad_payload(
        session_data,
        ["position.job_title", "company.name"],
        target_audience="Data Professionals",
    )
    assert payload["job_title"] == "Data Scientist (m/w/d)"
    assert payload["heading"] == "# Data Scientist (m/w/d) bei Example GmbH"
    assert document.splitlines()[0] == "# Data Scientist (m/w/d) bei Example GmbH"


def test_prepare_job_ad_payload_preserves_existing_marker() -> None:
    session_data = {
        "lang": "de",
        "position": {"job_title": "Data Scientist (m/w/d)"},
        "company": {"name": "Example GmbH"},
    }
    payload, document = _prepare_job_ad_payload(
        session_data,
        ["position.job_title", "company.name"],
        target_audience="Data Professionals",
    )
    assert payload["job_title"] == "Data Scientist (m/w/d)"
    assert payload["heading"] == "# Data Scientist (m/w/d) bei Example GmbH"
    assert document.splitlines()[0] == "# Data Scientist (m/w/d) bei Example GmbH"


def test_prepare_job_ad_payload_respects_configured_marker() -> None:
    session_data = {
        "lang": "de",
        "position": {"job_title": "Data Scientist"},
        "company": {"name": "Example GmbH"},
        "job_ad": {"gender_marker": "(gn)"},
    }
    payload, document = _prepare_job_ad_payload(
        session_data,
        ["position.job_title", "company.name"],
        target_audience="Data Professionals",
    )
    assert payload["job_title"] == "Data Scientist (gn)"
    assert payload["heading"] == "# Data Scientist (gn) bei Example GmbH"
    assert document.splitlines()[0] == "# Data Scientist (gn) bei Example GmbH"


def test_guess_company_brand() -> None:
    text = "Wir sind Cognitive Needs, ein Tech-Brand der Example GmbH"
    name, brand = guess_company(text)
    assert name == "Example GmbH"
    assert brand == "Cognitive Needs"


def test_guess_city_from_header() -> None:
    text = "Berlin | Hybrid | ab 01.10.2024"
    assert guess_city(text) == "Berlin"


def test_guess_city_from_standort_hint() -> None:
    text = "Standort: Stuttgart"
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)
    assert profile.location.primary_city == "Stuttgart"


@pytest.mark.skipif(
    not HAS_SPACY_PIPELINE,
    reason="spaCy German pipeline not installed (optional dependency)",
)
def test_spacy_fallback_city_and_country_lowercase() -> None:
    text = "wir suchen verstärkung in düsseldorf, deutschland mit sofortigem start"
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)
    assert profile.location.primary_city == "Düsseldorf"
    assert profile.location.country == "Germany"


def test_apply_basic_fallbacks_trims_city_tokens() -> None:
    text = "Arbeitsort: in Düsseldorf eine neue Filiale"
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)
    assert profile.location.primary_city == "Düsseldorf"


def test_apply_basic_fallbacks_populates_company_size() -> None:
    text = "Unser Unternehmen beschäftigt rund 3.370 Menschen an unserem Standort."
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)
    assert profile.company.size == "3370"


def test_apply_basic_fallbacks_uses_llm_city(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_llm(text: str) -> str:
        calls.append(text)
        return "Berlin"

    monkeypatch.setattr(heuristics, "_llm_extract_primary_city", fake_llm)
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), "Arbeitsort: ausschließlich remote")
    assert profile.location.primary_city == "Berlin"
    assert calls


@pytest.mark.skipif(
    not HAS_SPACY_PIPELINE,
    reason="spaCy German pipeline not installed (optional dependency)",
)
def test_spacy_fallback_uses_english_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "We are hiring in London, United Kingdom."

    class _Entity:
        def __init__(self, text: str, label: str) -> None:
            self.text = text
            self.label_ = label

    class _Doc:
        def __init__(self) -> None:
            self.ents = [
                _Entity("London", "GPE"),
                _Entity("United Kingdom", "GPE"),
            ]

    def fake_pipeline(value: str) -> _Doc:  # pragma: no cover - simple stub
        assert value == text
        return _Doc()

    attempted_models: list[str] = []

    def fake_optional_loader(model_name: str):
        attempted_models.append(model_name)
        if model_name == "en_core_web_sm":
            return fake_pipeline
        return None

    def fail_if_german_loaded() -> None:  # pragma: no cover - sanity guard
        raise AssertionError("German pipeline should not be loaded for English text")

    monkeypatch.setattr("nlp.entities._load_optional_pipeline", fake_optional_loader)
    monkeypatch.setattr("nlp.entities._load_de_pipeline", fail_if_german_loaded)

    profile = apply_basic_fallbacks(
        NeedAnalysisProfile(),
        text,
        metadata={"autodetect_language": "en"},
    )

    assert attempted_models == ["en_core_web_sm"]
    assert profile.location.primary_city == "London"
    assert profile.location.country == "United Kingdom"


def test_language_normalization_for_german_text() -> None:
    text = "Sprachen: Deutsch und Englisch"
    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)
    assert set(profile.requirements.languages_required) == {"German", "English"}


def test_language_extraction_handles_mandarin_optional() -> None:
    text = "Pflicht: Deutsch. Mandarin Chinese (wünschenswert)."

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert "German" in profile.requirements.languages_required
    assert "Chinese" in profile.requirements.languages_optional


def test_apply_basic_fallbacks_logs_city(caplog: pytest.LogCaptureFixture) -> None:
    text = "Standort: Stuttgart"
    with caplog.at_level(logging.INFO, logger="cognitive_needs.heuristics"):
        profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.location.primary_city == "Stuttgart"
    record = next(
        (rec for rec in caplog.records if getattr(rec, "heuristic_field", "") == "location.primary_city"),
        None,
    )
    assert record is not None
    assert record.heuristic_rule in {"city_regex", "city_entity", "city_regex_retry"}


def test_apply_basic_fallbacks_logs_benefits(caplog: pytest.LogCaptureFixture) -> None:
    text = "Benefits:\n- Lunch subsidy\n- Gym membership"
    with caplog.at_level(logging.INFO, logger="cognitive_needs.heuristics"):
        profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert profile.compensation.benefits == ["Lunch subsidy", "Gym membership"]
    record = next(
        (rec for rec in caplog.records if getattr(rec, "heuristic_field", "") == "compensation.benefits"),
        None,
    )
    assert record is not None
    assert record.heuristic_rule == "benefits_section"


def test_extract_benefits_from_text_bilingual_headings() -> None:
    text = """Wir bieten:
    - Unbefristeter Arbeitsvertrag
    - 30 Tage Urlaub
    - Firmenwagen
    """

    benefits = _extract_benefits_from_text(text)

    assert benefits == [
        "Unbefristeter Arbeitsvertrag",
        "30 Tage Urlaub",
        "Firmenwagen",
    ]


@pytest.mark.skipif(
    not HAS_SPACY_PIPELINE,
    reason="spaCy German pipeline not installed (optional dependency)",
)
def test_spacy_respects_invalid_metadata() -> None:
    text = "arbeitsort düsseldorf mit option in deutschland zu reisen"
    profile = NeedAnalysisProfile()
    profile.location.primary_city = "Berlin"
    metadata = {"invalid_fields": ["location.primary_city"]}
    profile = apply_basic_fallbacks(profile, text, metadata=metadata)
    assert profile.location.primary_city == "Düsseldorf"


@pytest.mark.skipif(
    not HAS_SPACY_PIPELINE,
    reason="spaCy German pipeline not installed (optional dependency)",
)
def test_spacy_does_not_override_high_confidence() -> None:
    text = "einsatzort düsseldorf"
    profile = NeedAnalysisProfile()
    profile.location.primary_city = "Berlin"
    metadata = {"high_confidence_fields": ["location.primary_city"]}
    profile = apply_basic_fallbacks(profile, text, metadata=metadata)
    assert profile.location.primary_city == "Berlin"


def test_basic_fallback_title_skips_company_banner() -> None:
    profile = NeedAnalysisProfile()
    profile.company.name = "Cognitive Needs GmbH"
    profile.location.primary_city = "Berlin"
    metadata = {
        "locked_fields": ["company.name", "location.primary_city"],
        "rules": {
            "company.name": {"value": "Cognitive Needs GmbH"},
            "location.primary_city": {"value": "Berlin"},
        },
    }
    text = "Cognitive Needs GmbH\nBerlin\nSenior Data Scientist (m/w/d)"
    updated = apply_basic_fallbacks(profile, text, metadata=metadata)
    assert updated.position.job_title == "Senior Data Scientist"
    assert updated.company.name == "Cognitive Needs GmbH"
    assert updated.location.primary_city == "Berlin"


def test_basic_fallback_title_skips_location_banner() -> None:
    profile = NeedAnalysisProfile()
    profile.location.primary_city = "Berlin"
    metadata = {
        "locked_fields": ["location.primary_city"],
        "rules": {"location.primary_city": {"value": "Berlin"}},
    }
    text = "Berlin | Germany\nSenior Data Scientist (m/w/d)"
    updated = apply_basic_fallbacks(profile, text, metadata=metadata)
    assert updated.position.job_title == "Senior Data Scientist"
    assert updated.location.primary_city == "Berlin"


def test_parse_extraction_city_alias() -> None:
    profile = parse_extraction('{"position": {"job_title": "Dev"}, "city": "Düsseldorf"}')
    assert profile.location.primary_city == "Düsseldorf"


def test_employment_and_start_date_fallbacks() -> None:
    text = "Festanstellung | Vollzeit\nHybrid (2-3 Tage/Woche im Office)\nStart ab 01.10.2024"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.job_type == "full_time"
    assert profile.employment.contract_type == "permanent"
    assert profile.employment.work_policy == "hybrid"
    assert profile.employment.remote_percentage == 50
    assert profile.meta.target_start_date == "2024-10-01"


def test_remote_days_remote_percentage_inference() -> None:
    text = "Werkstudent (m/w/d) Data Team\nArbeitsmodell: 3 Tage/Woche remote, 2 Tage im Büro"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.job_type == "working_student"
    assert profile.employment.work_policy == "hybrid"
    assert profile.employment.remote_percentage == 60


def test_remote_percentage_from_explicit_percent() -> None:
    text = "Arbeitsmodell: 80 % remote, 20 % Büro"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.remote_percentage == 80


def test_remote_percentage_from_days_without_week_suffix() -> None:
    text = "Hybrid role with 3 days remote and 2 days onsite"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.work_policy == "hybrid"
    assert profile.employment.remote_percentage == 60


def test_apprenticeship_job_type_detection() -> None:
    text = "Ausbildung zum Fachinformatiker (m/w/d) | Vollzeit"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.job_type == "apprenticeship"


def test_trainee_program_job_type_detection() -> None:
    text = "Traineeprogramm Vertrieb (all genders)"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.employment.job_type == "trainee_program"


def test_guess_employment_details_handles_homeoffice_percent() -> None:
    text = "Arbeitsmodell: 80% Homeoffice möglich"
    _, _, policy, percentage = guess_employment_details(text)
    assert policy == "remote"
    assert percentage == 80


def test_guess_employment_details_detects_work_anywhere() -> None:
    text = "We offer work from anywhere within Germany"
    _, _, policy, percentage = guess_employment_details(text)
    assert policy == "remote"
    assert percentage is None


def test_immediate_start_phrases() -> None:
    text = "Start zum nächstmöglichen Zeitpunkt (ASAP)"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.meta.target_start_date == "asap"


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


def test_benefit_section_extraction_sets_metadata() -> None:
    text = "Unsere Benefits:\n- 30 Urlaubstage\n- Sabbatical-Option\n- 1.000€ Lernbudget\n"
    profile = NeedAnalysisProfile()
    metadata: dict[str, object] = {"locked_fields": [], "high_confidence_fields": []}
    profile = apply_basic_fallbacks(profile, text, metadata=metadata)
    assert profile.compensation.benefits == [
        "30 Urlaubstage",
        "Sabbatical-Option",
        "1.000€ Lernbudget",
    ]
    assert "compensation.benefits" in metadata["locked_fields"]
    assert "compensation.benefits" in metadata["high_confidence_fields"]


def test_benefit_inline_list_extraction() -> None:
    text = "Benefits: 30 Urlaubstage, Sabbatical-Option, 1.000€ Lernbudget"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.compensation.benefits == [
        "30 Urlaubstage",
        "Sabbatical-Option",
        "1.000€ Lernbudget",
    ]


def test_benefit_section_handles_our_offer_heading() -> None:
    text = "Our Offer:\n· Flexible working hours\n· Remote stipend"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.compensation.benefits == [
        "Flexible working hours",
        "Remote stipend",
    ]


def test_benefit_section_handles_wir_bieten_heading() -> None:
    text = "Wir bieten:\n- Betriebliche Altersvorsorge\n- flexible Arbeitsmodelle"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.compensation.benefits == [
        "Betriebliche Altersvorsorge",
        "flexible Arbeitsmodelle",
    ]


def test_benefit_section_extracts_inline_comma_list() -> None:
    text = "Benefits, flexible Arbeitsmodelle und ein Umfeld, in dem Vielfalt gefördert wird."
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert "flexible Arbeitsmodelle und ein Umfeld" in profile.compensation.benefits
    assert any("Vielfalt" in entry for entry in profile.compensation.benefits)


def test_responsibility_fallbacks() -> None:
    text = "Dein Spielfeld:\n- Features entwickeln\n- Team unterstützen\n\nWas du mitbringst:\n- Python Erfahrung\n"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.responsibilities.items == [
        "Features entwickeln",
        "Team unterstützen",
    ]
    assert profile.position.role_summary == "Features entwickeln"


def test_responsibility_heading_variants() -> None:
    text = "Was dich erwartet:\n• Kunden beraten\n• Angebote erstellen\nDein Profil:\n• Kommunikationsstärke\n"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.responsibilities.items == [
        "Kunden beraten",
        "Angebote erstellen",
    ]


def test_multilingual_heading_mapping_german() -> None:
    text = (
        "Ihre Aufgaben:\n"
        "- Entwickeln neuer Features\n"
        "- Kunden betreuen\n\n"
        "Ihr Profil:\n"
        "- Erfahrung mit Python\n"
        "- Kommunikationsstärke\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert "Entwickeln neuer Features" in profile.responsibilities.items
    assert "Kunden betreuen" in profile.responsibilities.items

    requirement_entries = [
        *profile.requirements.hard_skills_required,
        *profile.requirements.soft_skills_required,
        *profile.requirements.tools_and_technologies,
    ]
    joined = " ".join(requirement_entries).lower()
    assert "python" in joined
    assert any("kommunikation" in entry.lower() for entry in requirement_entries)


def test_multilingual_heading_mapping_english() -> None:
    text = (
        "What you'll do:\n"
        "- Build backend services\n"
        "- Improve reliability\n\n"
        "What you'll need:\n"
        "- Java expertise\n"
        "- Problem-solving mindset\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert "Build backend services" in profile.responsibilities.items
    assert "Improve reliability" in profile.responsibilities.items

    requirement_entries = [
        *profile.requirements.hard_skills_required,
        *profile.requirements.soft_skills_required,
        *profile.requirements.tools_and_technologies,
    ]
    joined = " ".join(requirement_entries).lower()
    assert "java" in joined
    assert any("problem" in entry.lower() for entry in requirement_entries)


def test_responsibilities_extracted_from_jobbeschreibung_section() -> None:
    text = (
        "Jobbeschreibung\n"
        "- In dieser Rolle berätst du unsere Kunden zu Organisationsdesign und Transformationen\n"
        "- Du leitest Workshops mit Führungsteams\n\n"
        "Dein Profil:\n"
        "- Mehrjährige Erfahrung in Organisationsentwicklung\n"
        "- Kommunikationsstärke\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert len(profile.responsibilities.items) == 2
    assert "berätst du unsere kunden" in profile.responsibilities.items[0].lower()
    assert "leitest workshops" in profile.responsibilities.items[1].lower()

    all_requirements = sum(
        [
            profile.requirements.hard_skills_required,
            profile.requirements.soft_skills_required,
            profile.requirements.tools_and_technologies,
        ],
        [],
    )
    assert not any("berätst" in req.lower() for req in all_requirements)


def test_responsibility_and_skill_split_mixed_entries() -> None:
    text = (
        "Responsibilities:\n"
        "- You will lead a global team of analysts\n"
        "- Drive automation with Python expertise\n"
        "Qualifications:\n"
        "- 5+ years in analytics\n"
        "- Advanced SQL\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    assert len(profile.responsibilities.items) == 2
    assert any("lead a global team" in duty.lower() for duty in profile.responsibilities.items)
    assert any("drive automation" in duty.lower() for duty in profile.responsibilities.items)

    requirement_entries = [
        *profile.requirements.hard_skills_required,
        *profile.requirements.soft_skills_required,
        *profile.requirements.tools_and_technologies,
    ]
    assert any(req.lower() == "python" for req in requirement_entries)
    assert not any("lead a global team" in req.lower() for req in requirement_entries)


def test_inline_tech_stack_and_language_capture() -> None:
    text = (
        "Tech Stack: Python, TensorFlow, AWS\n"
        "Responsibilities:\n"
        "- Build and deploy machine learning models\n"
        "Requirements:\n"
        "- PMP certification\n"
        "- Fluent English and German\n"
    )

    profile = apply_basic_fallbacks(NeedAnalysisProfile(), text)

    tools = {tool.lower() for tool in profile.requirements.tools_and_technologies}
    assert {"aws", "tensorflow"}.issubset(tools)

    languages = {lang.lower() for lang in profile.requirements.languages_required}
    assert {"english", "german"}.issubset(languages)

    assert any("pmp" in cert.lower() for cert in profile.requirements.certifications)
    assert any("pmp" in cert.lower() for cert in profile.requirements.certificates)


def test_salary_single_value_detection() -> None:
    text = "Gehalt ab 75.000 € brutto"
    profile = NeedAnalysisProfile()
    profile = apply_basic_fallbacks(profile, text)
    assert profile.compensation.salary_min == 75000.0
    assert profile.compensation.salary_max == 75000.0
    assert profile.compensation.currency == "EUR"
    assert profile.compensation.salary_provided is True


def test_contact_extraction_prefers_hr_section() -> None:
    text = """
    Ihre Ansprechpartner:
    Benjamin Erben – HR Business Partner
    Telefon: 0211/123
    E-Mail: benjamin.erben@rheinbahn.de

    Max Mustermann – IT-Leitung
    E-Mail: m.m@rheinbahn.de
    """

    profile = NeedAnalysisProfile()
    profile.company.contact_email = "m.m@rheinbahn.de"

    updated = apply_basic_fallbacks(profile, text)

    assert updated.company.contact_name == "Benjamin Erben"
    assert updated.company.contact_email == "benjamin.erben@rheinbahn.de"
    assert updated.company.contact_phone == "0211 123"


def test_company_website_extraction() -> None:
    text = "Mehr über uns auf https://www.rheinbahn.de/ und in den sozialen Medien."

    profile = NeedAnalysisProfile()
    updated = apply_basic_fallbacks(profile, text)

    assert updated.company.website == "https://www.rheinbahn.de/"


def test_generic_contact_fallback() -> None:
    text = "Kontakt: careers@example.com oder telefonisch unter +49 123 456789."

    profile = NeedAnalysisProfile()
    updated = apply_basic_fallbacks(profile, text)

    assert updated.company.contact_email == "careers@example.com"
    assert updated.company.contact_phone == "+49 123 456789"


def test_city_extraction_from_address_line() -> None:
    text = "Headquarters: Hauptstrasse 12, 10115 Berlin"

    profile = NeedAnalysisProfile()
    updated = apply_basic_fallbacks(profile, text)

    assert updated.location.primary_city == "Berlin"


def test_numeric_context_extraction() -> None:
    text = "You will lead a team of 5 with 3 direct reports and up to 30% travel."

    profile = NeedAnalysisProfile()
    updated = apply_basic_fallbacks(profile, text)

    assert updated.position.team_size == 5
    assert updated.position.supervises == 3
    assert updated.employment.travel_share == 30
