import pytest

from openai_utils import call_chat_api


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.openai.api_key", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])
