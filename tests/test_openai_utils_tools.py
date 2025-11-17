"""Tests covering Responses vs. Chat routing with tool payloads."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict

import pytest

import config
import openai_utils.api as openai_api


@pytest.fixture(autouse=True)
def _fake_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure API calls see a configured key to keep _llm_disabled() false."""

    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(openai_api, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(openai_api, "client", None, raising=False)


@pytest.fixture(autouse=True)
def _disable_analysis_tool_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid importing and registering the full analysis tool suite in tests."""

    monkeypatch.setattr("core.analysis_tools.build_analysis_tools", lambda: ([], {}))


@pytest.fixture
def configure_responses_flags(monkeypatch: pytest.MonkeyPatch) -> Callable[[bool], None]:
    """Return a helper that synchronises the global API flags."""

    def _configure(allow_tools: bool) -> None:
        monkeypatch.setattr(config, "USE_CLASSIC_API", False, raising=False)
        monkeypatch.setattr(config, "USE_RESPONSES_API", True, raising=False)
        monkeypatch.setattr(openai_api.app_config, "USE_CLASSIC_API", False, raising=False)
        monkeypatch.setattr(openai_api.app_config, "USE_RESPONSES_API", True, raising=False)
        monkeypatch.setattr(config, "RESPONSES_ALLOW_TOOLS", allow_tools, raising=False)
        monkeypatch.setattr(openai_api, "RESPONSES_ALLOW_TOOLS", allow_tools, raising=False)

    return _configure


@pytest.fixture
def record_api_mode(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Capture the API mode used when invoking the OpenAI client stub."""

    captured: Dict[str, Any] = {}

    def _fake_create(payload: Dict[str, Any], *, api_mode: str | None = None) -> SimpleNamespace:
        mode = api_mode or ("chat" if openai_api.app_config.USE_CLASSIC_API else "responses")
        captured["mode"] = mode
        captured["api_mode"] = api_mode
        captured["payload"] = dict(payload)
        return SimpleNamespace(output=[], output_text="stub", usage={}, id="resp-test")

    monkeypatch.setattr(openai_api, "_create_response_with_timeout", _fake_create)
    return captured


def _basic_tool() -> dict[str, Any]:
    return {"type": "function", "function": {"name": "echo", "parameters": {"type": "object"}}}


def test_call_chat_api_forces_classic_when_responses_disallow_tools(
    configure_responses_flags: Callable[[bool], None],
    record_api_mode: Dict[str, Any],
) -> None:
    """Tools should force the classic API path when Responses disallows them."""

    configure_responses_flags(allow_tools=False)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hello"}],
        model="test-model",
        tools=[_basic_tool()],
    )

    assert record_api_mode["mode"] == "chat"
    assert result.content == "stub"


def test_call_chat_api_keeps_responses_when_tools_allowed(
    configure_responses_flags: Callable[[bool], None],
    record_api_mode: Dict[str, Any],
) -> None:
    """When Responses allows tools, stay in Responses mode for tool payloads."""

    configure_responses_flags(allow_tools=True)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hello"}],
        model="test-model",
        tools=[_basic_tool()],
    )

    assert record_api_mode["mode"] == "responses"
    assert result.content == "stub"
