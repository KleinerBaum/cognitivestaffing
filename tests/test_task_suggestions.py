import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import openai_utils
from openai_utils import ChatCallResult, suggest_responsibilities_for_role


def test_suggest_responsibilities_for_role(monkeypatch):
    payload = {
        "responsibilities": [
            "Lead roadmap",
            "Lead roadmap",
            "Coordinate stakeholders",
            "Ship releases",
            "Report KPIs",
            "Facilitate workshops",
            "Align with leadership",
            "Mentor peers",
        ]
    }

    def fake_call(messages, **kwargs):
        return ChatCallResult(json.dumps(payload), [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)
    out = suggest_responsibilities_for_role("Product Manager")
    assert out == [
        "Lead roadmap",
        "Coordinate stakeholders",
        "Ship releases",
        "Report KPIs",
        "Facilitate workshops",
    ]


def test_suggest_responsibilities_for_role_context(monkeypatch):
    captured: dict[str, str] = {}

    def fake_call(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult(json.dumps({"responsibilities": []}), [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)
    suggest_responsibilities_for_role(
        "Engineer",
        lang="de",
        company_name="Acme GmbH",
        team_structure="3er Produktteam",
        industry="SaaS",
        existing_responsibilities=["Code-Reviews", "Pair Programming"],
    )
    prompt = captured["prompt"]
    assert "Kontext:" in prompt
    assert "Acme GmbH" in prompt
    assert "3er Produktteam" in prompt
    assert "SaaS" in prompt
    assert "Bereits abgedeckte Aufgaben: Code-Reviews; Pair Programming" in prompt


def test_suggest_responsibilities_for_role_empty_title():
    assert suggest_responsibilities_for_role("") == []
