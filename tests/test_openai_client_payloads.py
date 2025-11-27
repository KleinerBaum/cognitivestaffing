from typing import Any

import config.models as model_config
from openai_utils.client import _prune_payload_for_api_mode


def test_prune_payload_preserves_messages_for_chat() -> None:
    """Chat mode pruning must keep ``messages`` so chat completions can run."""

    payload: dict[str, Any] = {
        "model": model_config.GPT4O_MINI,
        "messages": [{"role": "user", "content": "hi"}],
        "timeout": 5,
    }

    cleaned = _prune_payload_for_api_mode(payload, "chat")

    assert cleaned.get("messages") == payload["messages"]
    assert "input" not in cleaned
    assert cleaned.get("model") == model_config.GPT4O_MINI
