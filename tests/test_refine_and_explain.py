import config
import openai_utils
from openai_utils import ChatCallResult


def test_refine_document_passes_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["model"] = model
        return ChatCallResult("updated", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.refine_document("orig", "shorter", model=config.GPT5_MINI)
    assert "orig" in captured["prompt"]
    assert "shorter" in captured["prompt"]
    assert captured["model"] == config.GPT5_MINI
    assert out == "updated"


def test_what_happened_lists_keys(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["model"] = model
        return ChatCallResult("explanation", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    session = {
        "position.job_title": "Eng",
        "location.primary_city": "Berlin",
        "empty": "",
    }
    out = openai_utils.what_happened(session, "doc", doc_type="job ad", model=config.GPT5_MINI)
    assert "job ad" in captured["prompt"]
    assert "position.job_title" in captured["prompt"]
    assert "location.primary_city" in captured["prompt"]
    assert "empty" not in captured["prompt"]
    assert captured["model"] == config.GPT5_MINI
    assert out == "explanation"
