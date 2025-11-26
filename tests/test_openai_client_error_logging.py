from __future__ import annotations

from typing import Any

import pytest
from openai import OpenAIError

from openai_utils.api import _log_known_openai_error
from openai_utils.client import OpenAIClient


def test_log_known_openai_error_accepts_api_mode_keyword() -> None:
    error = OpenAIError("boom")

    # Should not raise even when api_mode is provided as keyword-only.
    _log_known_openai_error(error, api_mode="chat")


def test_execute_once_invokes_on_known_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient()
    error = OpenAIError("failure")
    calls: list[tuple[OpenAIError, str]] = []

    def _raise_error(*_args: Any, **_kwargs: Any) -> None:
        raise error

    def _on_known_error(err: OpenAIError, api_mode: str) -> None:
        calls.append((err, api_mode))

    monkeypatch.setattr(client, "_create_response_with_timeout", _raise_error)

    with pytest.raises(OpenAIError):
        client._execute_once({}, model=None, api_mode="responses", on_known_error=_on_known_error)

    assert calls == [(error, "responses")]
