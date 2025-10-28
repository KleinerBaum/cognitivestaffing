"""Tests covering logging and sanitisation in llm.client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from llm import client


class FakeLogger:
    """Minimal logger capturing warning messages for assertions."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, message: str, *args: object, **_: object) -> None:
        formatted = message % args if args else message
        self.messages.append(formatted)

    def debug(self, *args: object, **kwargs: object) -> None:  # noqa: D401 - interface compatibility
        """Ignore debug calls during tests."""
        _ = args, kwargs


def test_structured_extraction_logs_without_pii(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON decoding failures should log sanitised prompt metadata only."""

    fake_logger = FakeLogger()
    monkeypatch.setattr(client, "logger", fake_logger)
    monkeypatch.setattr(client, "USE_RESPONSES_API", False)
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *_, **__: SimpleNamespace(content="{"),
    )

    payload = {
        "messages": [
            {"role": "system", "content": "System prompt"},
            {
                "role": "user",
                "content": "Name: John Doe\nCompany: Example Labs\nEmail: john.doe@example.com",
            },
        ],
        "model": "gpt-4o-mini",
    }

    with pytest.raises(ValueError, match="valid JSON"):
        client._structured_extraction(payload)

    assert fake_logger.messages, "expected at least one warning to be logged"
    assert any("latest_user_hash=" in msg for msg in fake_logger.messages)
    for message in fake_logger.messages:
        assert "John" not in message
        assert "Example" not in message
        assert "john.doe@example.com" not in message
