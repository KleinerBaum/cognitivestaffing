from types import SimpleNamespace

import pytest

import config


@pytest.fixture(autouse=True)
def reset_missing_flag(monkeypatch):
    monkeypatch.setattr(config, "_missing_api_key_logged", False, raising=False)
    yield


def test_openai_key_resolution_order(monkeypatch, caplog):
    fake_secrets: dict[str, object] = {"OPENAI_API_KEY": "secret-key"}
    fake_streamlit = SimpleNamespace(secrets=fake_secrets)
    monkeypatch.setattr(config, "st", fake_streamlit, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    # Direct Streamlit secret wins over environment variables.
    assert config.get_openai_api_key() == "secret-key"

    # Nested openai section is used when the top-level key is missing.
    fake_secrets.pop("OPENAI_API_KEY")
    fake_secrets["openai"] = {"OPENAI_API_KEY": "section-key"}
    assert config.get_openai_api_key() == "section-key"

    # Environment variable is the final fallback.
    fake_secrets["openai"].pop("OPENAI_API_KEY")  # type: ignore[index]
    assert config.get_openai_api_key() == "env-key"

    # When no key is available a single info log is emitted.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake_secrets.clear()
    caplog.clear()
    with caplog.at_level("INFO"):
        assert config.get_openai_api_key() == ""
    assert "LLM-powered features are disabled" in caplog.text

    # Subsequent calls remain silent until a key is set again.
    caplog.clear()
    assert config.get_openai_api_key() == ""
    assert caplog.text == ""

    # Setting a key resets the log guard.
    fake_secrets["OPENAI_API_KEY"] = "restored"
    assert config.get_openai_api_key() == "restored"
