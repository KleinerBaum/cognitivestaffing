import json

import pytest
import config.models as model_config
from llm import client
from models.need_analysis import NeedAnalysisProfile


class _FakeParser:
    format_instructions = ""

    def parse(self, content: str):
        return NeedAnalysisProfile(), json.loads(content)


class _FakeChatResult:
    def __init__(self, content: str):
        self.content = content
        self.usage = {}
        self.response_id = "chat"
        self.raw_response = None


def test_responses_schema_error_switches_to_chat_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"chat": 0, "responses": 0}

    def _raise_invalid_schema(*_: object, **__: object):
        calls["responses"] += 1
        return None

    def _fake_chat_api(*_: object, **__: object) -> _FakeChatResult:
        calls["chat"] += 1
        return _FakeChatResult(json.dumps({"title": "Engineer"}))

    monkeypatch.setattr(client, "call_responses_safe", _raise_invalid_schema)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat_api)
    monkeypatch.setattr(client, "get_need_analysis_output_parser", lambda: _FakeParser())
    monkeypatch.setattr(client, "_responses_api_enabled", lambda: True)
    monkeypatch.setattr(client, "_strict_extraction_enabled", lambda: True)

    outcome = client._structured_extraction(
        {
            "messages": [{"role": "user", "content": "text"}],
            "model": model_config.GPT4O_MINI,
            "reasoning_effort": None,
            "verbosity": None,
            "retries": 0,
            "source_text": "",
        }
    )

    assert calls["responses"] == 1
    assert calls["chat"] == 1
    assert json.loads(outcome.content)["title"] == "Engineer"
    assert outcome.low_confidence is True
