from typing import Any

from openai_utils.client import _prune_payload_for_api_mode


def test_prune_payload_preserves_messages_for_chat() -> None:
    """Chat mode pruning must keep ``messages`` so chat completions can run."""

    payload: dict[str, Any] = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "timeout": 5,
    }

    cleaned = _prune_payload_for_api_mode(payload, "chat")

    assert cleaned.get("messages") == payload["messages"]
    assert "input" not in cleaned
    assert cleaned.get("model") == "gpt-4o-mini"
