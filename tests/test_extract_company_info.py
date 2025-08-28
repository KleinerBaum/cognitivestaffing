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

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    result = openai_utils.extract_company_info("dummy text")
    assert result == {
        "name": "Acme Corp",
        "location": "Berlin, Germany",
        "mission": "Make widgets greener",
        "culture": "Collaborative and inclusive",
    }
