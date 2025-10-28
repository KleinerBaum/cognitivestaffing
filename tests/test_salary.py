from importlib import import_module
from types import SimpleNamespace
from typing import Any

from constants.keys import StateKeys, UIKeys


def test_estimate_salary_expectation_sets_fallback_source(monkeypatch) -> None:
    salary = import_module("sidebar.salary")

    fake_state: dict[str, Any] = {}
    fake_streamlit = SimpleNamespace(session_state=fake_state)
    monkeypatch.setattr(salary, "st", fake_streamlit)
    monkeypatch.setattr(salary, "call_chat_api", None)
    monkeypatch.setattr(salary, "build_extraction_tool", None)

    profile = {
        "position": {"job_title": "Software Developer"},
        "location": {"primary_city": "Düsseldorf"},
    }
    fake_state[StateKeys.PROFILE] = profile

    salary.estimate_salary_expectation()

    estimate = fake_state.get(UIKeys.SALARY_ESTIMATE)
    assert estimate is not None
    assert estimate.get("source") == "fallback"


def test_sidebar_benefits_use_fallback_when_llm_empty(monkeypatch) -> None:
    salary = import_module("sidebar.salary")

    fallback = ["Flexible working hours", "Remote-friendly work"]
    fake_state: dict[str, Any] = {
        StateKeys.BENEFIT_SUGGESTIONS: {"llm": [], "fallback": fallback}
    }
    fake_streamlit = SimpleNamespace(session_state=fake_state)
    monkeypatch.setattr(salary, "st", fake_streamlit)

    bundle = salary.resolve_sidebar_benefits(lang="en", industry="tech")

    assert bundle.source == "fallback"
    assert bundle.suggestions == fallback
