from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from openai_utils import server


def _fake_run_result(text: str) -> SimpleNamespace:
    raw_item = {
        "id": "msg-1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }
    return SimpleNamespace(new_items=[SimpleNamespace(raw_item=raw_item)])


def test_user_message_event(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def _run(agent: Any, input: Any, **_: Any) -> SimpleNamespace:
        captured["input"] = input
        return _fake_run_result("Hello")

    monkeypatch.setattr(server, "_get_agent", lambda: "agent")
    monkeypatch.setattr(server.Runner, "run", _run)

    client = TestClient(server.app)
    response = client.post(
        "/chatkit/respond", json={"type": "user_message", "text": "Hi", "conversation_id": "conv-123"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["conversation_id"] == "conv-123"
    assert captured["input"][0]["role"] == "user"
    assert captured["input"][0]["content"][0]["text"] == "Hi"
    assert payload["messages"][0]["content"][0]["text"] == "Hello"


def test_action_event_invokes_function_output(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    async def _run(agent: Any, input: Any, **_: Any) -> SimpleNamespace:
        captured["input"] = input
        return _fake_run_result("Processed")

    monkeypatch.setattr(server, "_get_agent", lambda: "agent")
    monkeypatch.setattr(server.Runner, "run", _run)

    client = TestClient(server.app)
    response = client.post(
        "/chatkit/respond",
        json={
            "type": "action_invoked",
            "conversation_id": "conv-456",
            "action": {"id": "tool-1", "payload": {"foo": "bar"}},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["conversation_id"] == "conv-456"
    assert captured["input"][0]["type"] == "function_call_output"
    assert captured["input"][0]["call_id"] == "tool-1"
    assert "foo" in captured["input"][0]["output"]
    assert payload["messages"][0]["content"][0]["text"] == "Processed"


def test_unknown_event_returns_error(monkeypatch: Any) -> None:
    client = TestClient(server.app)
    response = client.post("/chatkit/respond", json={"type": "unknown"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "Unsupported" in payload["error"]
