import json

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import question_logic
from question_logic import ask_followups


def test_ask_followups_parses_message(monkeypatch):
    """ask_followups should parse JSON content from call_chat_api result."""

    class _FakeMessage:
        def __init__(self) -> None:
            self.content = json.dumps({"questions": [{"field": "f", "question": "?"}]})

    monkeypatch.setattr(question_logic, "call_chat_api", lambda *a, **k: _FakeMessage())
    out = ask_followups({})
    assert out == {"questions": [{"field": "f", "question": "?"}]}
