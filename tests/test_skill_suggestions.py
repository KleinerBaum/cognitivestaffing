import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import config
import openai_utils
from openai_utils import ChatCallResult, suggest_skills_for_role


def fake_call(messages, **kwargs):
    payload = json.dumps(
        {
            "tools_and_technologies": [f"T{i}" for i in range(1, 12)],
            "hard_skills": ["H1", "H1", "H2"],
            "soft_skills": ["S1", "S2"],
            "certificates": ["CertA", "CertB"],
        }
    )
    return ChatCallResult(payload, [], {})


def test_suggest_skills_for_role(monkeypatch):
    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call)
    monkeypatch.setattr("core.esco_utils.normalize_skills", lambda skills, lang="en": skills)
    out = suggest_skills_for_role("Engineer")
    assert out["tools_and_technologies"] == [f"T{i}" for i in range(1, 11)]
    assert out["hard_skills"] == ["H1", "H2"]
    assert out["soft_skills"] == ["S1", "S2"]
    assert out["certificates"] == ["CertA", "CertB"]


def test_suggest_skills_for_role_empty():
    out = suggest_skills_for_role("")
    assert out == {
        "tools_and_technologies": [],
        "hard_skills": [],
        "soft_skills": [],
        "certificates": [],
    }


def test_suggest_skills_for_role_focus_terms(monkeypatch):
    captured: dict[str, str] = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        empty_payload = {
            "tools_and_technologies": [],
            "hard_skills": [],
            "soft_skills": [],
            "certificates": [],
        }
        return ChatCallResult(json.dumps(empty_payload), [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    suggest_skills_for_role("Engineer", focus_terms=["Cloud", "Security"])
    assert "Cloud, Security" in captured["prompt"]


def test_responses_skill_suggestions_fall_back_to_legacy(monkeypatch):
    import llm.suggestions as responses_suggestions

    legacy_payload = {
        "tools_and_technologies": ["Legacy Tool"],
        "hard_skills": ["Legacy Hard"],
        "soft_skills": ["Legacy Soft"],
        "certificates": ["Legacy Cert"],
    }

    monkeypatch.setattr(responses_suggestions, "call_responses_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        "openai_utils.suggest_skills_for_role",
        lambda *args, **kwargs: legacy_payload,
    )

    out = responses_suggestions.suggest_skills_for_role("Engineer")
    assert out == legacy_payload


def test_responses_benefit_suggestions_return_static_shortlist(monkeypatch):
    import llm.suggestions as responses_suggestions

    static_shortlist = ["Static One", "Static Two"]

    monkeypatch.setattr(responses_suggestions, "call_responses_safe", lambda *a, **k: None)
    monkeypatch.setattr(
        "core.suggestions.get_static_benefit_shortlist",
        lambda **_kwargs: static_shortlist,
    )

    out = responses_suggestions.suggest_benefits("Engineer", lang="en")
    assert out == static_shortlist


def test_skill_suggestions_log_warning_on_failure(monkeypatch, caplog):
    import llm.suggestions as responses_suggestions

    caplog.set_level("WARNING")

    legacy_payload = {
        "tools_and_technologies": ["Legacy Tool"],
        "hard_skills": ["Legacy Hard"],
        "soft_skills": ["Legacy Soft"],
        "certificates": ["Legacy Cert"],
    }

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Responses failure")

    monkeypatch.setattr("llm.openai_responses.call_responses", _boom)
    monkeypatch.setattr(
        "openai_utils.suggest_skills_for_role",
        lambda *args, **kwargs: legacy_payload,
    )

    out = responses_suggestions.suggest_skills_for_role("Engineer")
    assert out == legacy_payload
    assert any("skill suggestion" in record.getMessage() for record in caplog.records if record.levelname == "WARNING")


def test_benefit_suggestions_log_warning_on_failure(monkeypatch, caplog):
    import llm.suggestions as responses_suggestions

    caplog.set_level("WARNING")

    static_shortlist = ["Static One", "Static Two"]

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Responses failure")

    monkeypatch.setattr("llm.openai_responses.call_responses", _boom)
    monkeypatch.setattr(
        "core.suggestions.get_static_benefit_shortlist",
        lambda **_kwargs: static_shortlist,
    )

    out = responses_suggestions.suggest_benefits("Engineer", lang="en")
    assert out == static_shortlist
    assert any(
        "benefit suggestion" in record.getMessage() for record in caplog.records if record.levelname == "WARNING"
    )


def test_skill_suggestions_use_legacy_when_api_disabled(monkeypatch, caplog) -> None:
    import llm.suggestions as responses_suggestions

    caplog.set_level("INFO", logger="llm.suggestions")
    caplog.clear()

    responses_payload = {
        "tools_and_technologies": ["Responses Tool"],
        "hard_skills": ["Responses Hard"],
        "soft_skills": ["Responses Soft"],
        "certificates": ["Responses Cert"],
    }
    calls = {"responses": 0}

    def _fake_responses(*_args, **_kwargs):
        calls["responses"] += 1
        return responses_payload

    monkeypatch.setattr("llm.suggestions.call_responses_safe", _fake_responses)
    monkeypatch.setattr(
        "openai_utils.suggest_skills_for_role",
        lambda *args, **kwargs: responses_payload,
    )

    out = responses_suggestions.suggest_skills_for_role("Engineer")
    assert out == responses_payload
    assert calls["responses"] == 1
    assert not any("legacy chat API" in record.getMessage() for record in caplog.records)


def test_benefit_suggestions_use_legacy_when_api_disabled(monkeypatch, caplog) -> None:
    import llm.suggestions as responses_suggestions

    caplog.set_level("INFO", logger="llm.suggestions")
    caplog.clear()

    responses_payload = ["Responses Benefit"]
    calls = {"responses": 0}

    def _fake_responses(*_args, **_kwargs):
        calls["responses"] += 1
        return responses_payload

    monkeypatch.setattr("llm.suggestions.call_responses_safe", _fake_responses)
    monkeypatch.setattr(
        "openai_utils.suggest_benefits",
        lambda *args, **kwargs: responses_payload,
    )

    out = responses_suggestions.suggest_benefits(
        "Engineer",
        industry="Tech",
        existing_benefits="",
        lang="en",
    )
    assert out == responses_payload
    assert calls["responses"] == 1
    assert not any("legacy chat API" in record.getMessage() for record in caplog.records)
