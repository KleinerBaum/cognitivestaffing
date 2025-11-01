from llm.context import (
    build_extract_messages,
    build_preanalysis_messages,
    MAX_CHAR_BUDGET,
)
from llm.prompts import PreExtractionInsights, SYSTEM_JSON_EXTRACTOR
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
