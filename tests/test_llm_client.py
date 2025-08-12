import json

import llm.client as client


def fake_create(**kwargs):
    if client.MODE == "function":
        return {
            "choices": [
                {"message": {"function_call": {"arguments": json.dumps({"job_title": "x"})}}}
            ]
        }
    return {"choices": [{"message": {"content": "{}"}}]}


def test_extract_json_smoke(monkeypatch):
    monkeypatch.setattr(client.openai.ChatCompletion, "create", fake_create)
    out = client.extract_json("text")
    assert isinstance(out, str) and out != ""
