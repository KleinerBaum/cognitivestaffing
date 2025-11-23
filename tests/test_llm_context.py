from llm.context import (
    build_extract_messages,
    build_preanalysis_messages,
    MAX_CHAR_BUDGET,
)
from llm.prompts import (
    FIELDS_ORDER_QUICK,
    PreExtractionInsights,
    SECTION_PRIMER,
    SYSTEM_JSON_EXTRACTOR,
    _extract_section_hints,
)
from nlp.prepare_text import truncate_smart


def test_build_messages_include_title_company_and_url():
    msgs = build_extract_messages(
        "body",
        title="Engineer",
        company="Acme Corp",
        url="http://x",
    )
    system_content = msgs[0]["content"]
    assert system_content.startswith(SYSTEM_JSON_EXTRACTOR)
    assert "Use the following structured output format." in system_content
    user = msgs[1]["content"]
    assert "Title: Engineer" in user
    assert "Company: Acme Corp" in user
    assert "Url: http://x" in user


def test_build_messages_include_locked_fields():
    msgs = build_extract_messages(
        "body",
        locked_fields={
            "position.job_title": "Engineer",
            "company.name": "Acme Corp",
        },
    )
    system = msgs[0]["content"]
    assert "Keep locked fields unchanged" in system
    assert "Use the following structured output format." in system
    user = msgs[1]["content"]
    assert "Locked fields (preserve existing values):" in user
    assert "  - position.job_title" in user
    assert "  - company.name" in user
    assert "- position.job_title: Engineer" not in user


def test_locked_fields_are_excluded_from_field_list():
    msgs = build_extract_messages(
        "body",
        locked_fields={
            "company.name": "Acme Corp",
        },
    )
    user = msgs[1]["content"]
    lines = user.splitlines()
    field_bullets = [line for line in lines if line.startswith("- ") and ":" not in line]
    assert all("company.name" not in line for line in field_bullets)
    assert any("company.brand_name" in line for line in field_bullets)
    assert "Focus on the remaining unlocked fields:" in user


def test_field_list_falls_back_when_all_locked():
    from llm.prompts import FIELDS_ORDER

    locked_fields = {field: "x" for field in FIELDS_ORDER}
    msgs = build_extract_messages("body", locked_fields=locked_fields)
    user = msgs[1]["content"]
    assert "Focus on the following fields:" in user
    # When all fields are locked we still show the schema reference.
    assert "- company.name" in user


def test_build_messages_truncates_text():
    text = "line\n" * 1000
    msgs = build_extract_messages(text)
    truncated = truncate_smart(text, MAX_CHAR_BUDGET)
    assert truncated in msgs[1]["content"]


def test_build_messages_include_insights_block():
    insights = PreExtractionInsights(
        summary="Compensation and responsibilities are detailed.",
        relevant_fields=["compensation.salary_min", "responsibilities.items"],
        missing_fields=["company.website"],
    )
    msgs = build_extract_messages("body", insights=insights)
    user = msgs[1]["content"]
    assert "Pre-analysis highlights:" in user
    assert "Likely evidence for these fields:" in user
    assert "compensation.salary_min" in user
    assert "Potential gaps or missing details:" in user


def test_build_preanalysis_messages_include_extras():
    msgs = build_preanalysis_messages(
        "body",
        title="Engineer",
        company="Acme",
        url="https://example.com",
    )
    assert msgs[0]["content"]
    user = msgs[1]["content"]
    assert "Title: Engineer" in user
    assert "Company: Acme" in user
    assert "Schema reference" in user


def test_quick_mode_uses_reduced_field_list(monkeypatch):
    monkeypatch.setattr("llm.context.get_reasoning_mode", lambda: "quick")
    msgs = build_extract_messages("body")
    user = msgs[1]["content"]
    assert "- position.job_title" in user
    assert "- process.onboarding_process" not in user
    # ensure we still mention at least one quick field
    assert any(field in user for field in (f"- {name}" for name in FIELDS_ORDER_QUICK))


def test_quick_mode_shortens_preanalysis_reference(monkeypatch):
    monkeypatch.setattr("llm.context.get_reasoning_mode", lambda: "quick")
    msgs = build_preanalysis_messages("body")
    user = msgs[1]["content"]
    assert "- position.job_title" in user
    assert "- process.onboarding_process" not in user


def test_section_hints_are_injected_when_headings_exist():
    text = """Aufgaben:
    - Team führen
    - Backlog priorisieren

    Anforderungen:
    - Python
    - Erfahrung mit APIs
    """
    msgs = build_extract_messages(text)
    user = msgs[1]["content"]
    assert "Section cues detected via rule-based scan" in user
    assert "Team führen" in user
    assert "Erfahrung mit APIs" in user
    assert SECTION_PRIMER in user


def test_german_jobbeschreibung_and_benefits_are_split_correctly():
    text = """Jobbeschreibung:
    - Leiten von Projekten
    - Koordination von Teams

    Wir bieten:
    - 30 Tage Urlaub
    - Flexible Arbeitszeiten
    """

    sections = _extract_section_hints(text)

    assert sections.get("requirements") is None
    assert sections.get("responsibilities") == [
        "Leiten von Projekten\nKoordination von Teams",
    ]


def test_task_list_and_key_responsibilities_headings_detected():
    text = """Task List:
    - Develop dashboards
    - Maintain ETL pipelines

    Key Responsibilities
    1. Partner with stakeholders
    2. Translate business needs into data models

    Requirements:
    - SQL
    - Python
    """

    sections = _extract_section_hints(text)

    assert sections.get("requirements") == ["SQL\nPython"]
    assert sections.get("responsibilities") == [
        "Develop dashboards\nMaintain ETL pipelines",
        "1. Partner with stakeholders\n2. Translate business needs into data models",
    ]


def test_your_mission_and_ihr_profil_headings_detected():
    text = """Your Mission
    - Build integrations
    - Ship features

    Ihr Profil
    - Erfahrung mit Python
    - Freude an Zusammenarbeit
    """

    sections = _extract_section_hints(text)

    assert sections.get("responsibilities") == ["Build integrations\nShip features"]
    assert sections.get("requirements") == ["Erfahrung mit Python\nFreude an Zusammenarbeit"]
