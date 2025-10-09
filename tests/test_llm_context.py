from llm.context import build_extract_messages, MAX_CHAR_BUDGET
from llm.prompts import SYSTEM_JSON_EXTRACTOR
from nlp.prepare_text import truncate_smart


def test_build_messages_include_title_company_and_url():
    msgs = build_extract_messages(
        "body",
        title="Engineer",
        company="Acme Corp",
        url="http://x",
    )
    assert msgs[0]["content"] == SYSTEM_JSON_EXTRACTOR
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
    assert "Keep provided locked values unchanged" in system
    user = msgs[1]["content"]
    assert "Locked values (reuse exactly):" in user
    assert "- position.job_title: Engineer" in user
    assert "- company.name: Acme Corp" in user


def test_build_messages_truncates_text():
    text = "line\n" * 1000
    msgs = build_extract_messages(text)
    truncated = truncate_smart(text, MAX_CHAR_BUDGET)
    assert truncated in msgs[1]["content"]
