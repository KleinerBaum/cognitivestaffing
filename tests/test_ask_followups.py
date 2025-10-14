import json

from pathlib import Path
import sys
from typing import Any

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))
import question_logic
from question_logic import ask_followups


def test_ask_followups_parses_message(monkeypatch):
    """ask_followups should parse JSON content from call_chat_api result."""

    class _FakeMessage:
        def __init__(self) -> None:
            self.content = json.dumps(
                {
                    "questions": [
                        {
                            "field": "f",
                            "question": "?",
                            "priority": "normal",
                        }
                    ]
                }
            )

    monkeypatch.setattr(question_logic, "call_chat_api", lambda *a, **k: _FakeMessage())
    out = ask_followups({})
    assert out == {"questions": [{"field": "f", "question": "?", "priority": "normal", "suggestions": []}]}


def test_ask_followups_enables_vector_store(monkeypatch):
    """Vector store IDs should trigger file search tool usage."""

    st.session_state.clear()
    st.session_state["vector_store_id"] = "vs123"

    captured: dict[str, Any] = {}

    class _FakeMessage:
        content = json.dumps({"questions": []})

    def fake_call(messages, **kwargs):
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        return _FakeMessage()

    monkeypatch.setattr(question_logic, "call_chat_api", fake_call)

    out = ask_followups({})

    assert out == {"questions": []}
    assert captured["tools"] == [{"type": "file_search", "vector_store_ids": ["vs123"]}]
    assert captured["tool_choice"] == "auto"
