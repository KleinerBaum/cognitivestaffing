from llm.context import build_extract_messages, MAX_CHAR_BUDGET
from llm.prompts import SYSTEM_JSON_EXTRACTOR
from nlp.prepare_text import truncate_smart


def test_build_messages_includes_title_and_url():
    msgs = build_extract_messages("body", title="Engineer", url="http://x")
    assert msgs[0]["content"] == SYSTEM_JSON_EXTRACTOR
    user = msgs[1]["content"]
    assert "Engineer" in user
    assert "http://x" in user


def test_build_messages_truncates_text():
    text = "line\n" * 1000
    msgs = build_extract_messages(text)
    truncated = truncate_smart(text, MAX_CHAR_BUDGET)
    assert truncated in msgs[1]["content"]
