"""Tests for company info extraction helper."""

import json

import openai_utils
from openai_utils import ChatCallResult


def test_extract_company_info_parses_json(monkeypatch):
    """Parse JSON returned by the model into a dictionary."""

    def fake_call_chat_api(messages, **kwargs):
        payload = json.dumps(
            {
                "name": "Acme Corp",
                "location": "Berlin, Germany",
                "mission": "Make widgets greener",
                "culture": "Collaborative and inclusive",
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
        ]
    )
