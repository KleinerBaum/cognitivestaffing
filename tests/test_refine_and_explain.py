import openai_utils


def test_refine_document_passes_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["model"] = model
        return "updated"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    out = openai_utils.refine_document("orig", "shorter", model="gpt-4")
    assert "orig" in captured["prompt"]
    assert "shorter" in captured["prompt"]
    assert captured["model"] == "gpt-4"
    assert out == "updated"


def test_what_happened_lists_keys(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["model"] = model
        return "explanation"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    session = {"job_title": "Eng", "location": "Berlin", "empty": ""}
    out = openai_utils.what_happened(session, "doc", doc_type="job ad", model="gpt-4")
    assert "job ad" in captured["prompt"]
    assert "job_title" in captured["prompt"]
    assert "location" in captured["prompt"]
    assert "empty" not in captured["prompt"]
    assert captured["model"] == "gpt-4"
    assert out == "explanation"
