"""Tests for company info extraction helper."""

import json

import pytest

import openai_utils
from openai_utils import ChatCallResult


pytestmark = pytest.mark.integration


def test_extract_company_info_parses_json(monkeypatch):
    """Parse JSON returned by the model into a dictionary."""

    def fake_call_chat_api(messages, **kwargs):
        payload = json.dumps(
            {
                "name": "Acme Corp",
                "location": "Berlin, Germany",
                "mission": "Make widgets greener",
                "culture": "Collaborative and inclusive",
                "size": "250 employees",
                "website": "https://acme.example",
            }
        )
        return ChatCallResult(payload, [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    result = openai_utils.extract_company_info("dummy text")
    assert result == {
        "name": "Acme Corp",
        "location": "Berlin, Germany",
        "mission": "Make widgets greener",
        "culture": "Collaborative and inclusive",
        "size": "250 employees",
        "website": "https://acme.example",
    }


def test_extract_company_info_required_keys(monkeypatch):
    """Ensure all expected fields are marked as required in the schema."""

    captured_kwargs: dict[str, object] = {}

    def fake_call_chat_api(messages, **kwargs):
        captured_kwargs.update(kwargs)
        payload = json.dumps(
            {
                "name": "Acme Corp",
                "location": "Berlin, Germany",
                "mission": "Make widgets greener",
                "culture": "Collaborative and inclusive",
                "size": "250 employees",
                "website": "https://acme.example",
            }
        )
        return ChatCallResult(payload, [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    openai_utils.extract_company_info("dummy text")

    json_schema = captured_kwargs.get("json_schema")
    assert isinstance(json_schema, dict)
    schema = json_schema.get("schema")
    assert isinstance(schema, dict)
    properties = schema.get("properties")
    assert isinstance(properties, dict)
    required = schema.get("required")
    assert (
        required
        == list(properties.keys())
        == [
            "name",
            "location",
            "mission",
            "culture",
            "size",
            "website",
        ]
    )
    assert captured_kwargs.get("tools") == [{"type": "web_search", "name": "web_search"}]
    assert captured_kwargs.get("tool_choice") is None


def test_extract_company_info_with_vector_store(monkeypatch):
    """Advertise file search when a vector store ID is provided."""

    captured_kwargs: dict[str, object] = {}

    def fake_call_chat_api(messages, **kwargs):
        captured_kwargs.update(kwargs)
        payload = json.dumps(
            {
                "name": "Acme Corp",
                "location": "Berlin, Germany",
                "mission": "Make widgets greener",
                "culture": "Collaborative and inclusive",
                "size": "250 employees",
                "website": "https://acme.example",
            }
        )
        return ChatCallResult(payload, [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)

    openai_utils.extract_company_info("dummy text", vector_store_id="store-1")

    tools = captured_kwargs.get("tools")
    assert isinstance(tools, list)
    assert tools, "Expected file_search tool definition"
    first_tool = tools[0]
    assert first_tool.get("type") == "file_search"
    assert first_tool.get("name") == "file_search"
    assert first_tool.get("vector_store_ids") == ["store-1"]
    assert captured_kwargs.get("tool_choice") == "auto"


def test_extract_company_info_fallback_keyword(monkeypatch):
    """Fallback still extracts mission and culture hints when the API fails."""

    def failing_call_chat_api(messages, **kwargs):  # noqa: D401 - inline helper
        raise RuntimeError("boom")

    monkeypatch.setattr(openai_utils.api, "call_chat_api", failing_call_chat_api)

    sample = "Our mission is to make hiring joyful.\nWe love a collaborative culture."

    result = openai_utils.extract_company_info(sample)

    assert result == {
        "mission": "Our mission is to make hiring joyful.",
        "culture": "We love a collaborative culture.",
    }
