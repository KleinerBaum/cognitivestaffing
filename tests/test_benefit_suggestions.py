from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parent.parent))

import openai_utils
from openai_utils import ChatCallResult, suggest_benefits


def fake_call(messages, **kwargs):
    payload = json.dumps(["A", "B", "A", ""])  # duplicates and blank
    return ChatCallResult(payload, [], {})


def test_suggest_benefits(monkeypatch):
    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call)
    out = suggest_benefits("Engineer", existing_benefits="B")
    assert out == ["A"]


def test_suggest_benefits_empty():
    assert suggest_benefits("") == []
