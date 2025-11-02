from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from constants.keys import StateKeys, UIKeys


salary = import_module("sidebar.salary")


def test_fallback_salary_handles_country_name(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_benchmark(role: str, country: str = "US") -> dict[str, str]:
        captured["role"] = role
        captured["country"] = country
        return {"salary_range": "40000-50000"}

    monkeypatch.setattr(salary, "get_salary_benchmark", fake_benchmark)

    profile = {
        "position": {"job_title": "Software Developer"},
        "location": {"country": "Germany"},
    }

    inputs = salary._collect_inputs(profile)
    result, explanation = salary._fallback_salary(inputs)

    assert captured["country"] == "DE"
    assert result == {"salary_min": 40000.0, "salary_max": 50000.0, "currency": "EUR"}

    assert isinstance(explanation, list)
    keys = [entry.get("key") for entry in explanation]
    assert "benchmark_role" in keys
    source_entry = explanation[0]
    assert source_entry["key"] == "source"
    assert source_entry.get("impact", {}).get("note") == "fallback_source"
    salary_min_entry = next(item for item in explanation if item.get("key") == "salary_min")
    assert salary_min_entry.get("impact", {}).get("note") == "no_user_input"


def test_estimate_uses_city_when_country_missing(monkeypatch) -> None:
    monkeypatch.setattr(salary, "call_chat_api", None)
    monkeypatch.setattr(salary, "build_extraction_tool", None)

    fake_state: dict[str, Any] = {}
    fake_streamlit = SimpleNamespace(session_state=fake_state)
    monkeypatch.setattr(salary, "st", fake_streamlit)

    profile = {
        "position": {"job_title": "Software Developer"},
        "location": {"primary_city": "Düsseldorf"},
    }

    fake_state[StateKeys.PROFILE] = profile

    salary.estimate_salary_expectation()

    estimate = fake_state[UIKeys.SALARY_ESTIMATE]
    assert estimate is not None
    assert estimate["source"] == "fallback"
    assert estimate["salary_min"] == 60000.0
    assert estimate["salary_max"] == 85000.0
    assert estimate["currency"] == "EUR"

    explanation = fake_state[UIKeys.SALARY_EXPLANATION]
    assert isinstance(explanation, list)
    assert any(item.get("key") == "benchmark_country" for item in explanation)


def test_fallback_salary_handles_german_product_developer() -> None:
    profile = {
        "position": {"job_title": "Produktentwickler innovative Mobilitätskonzepte"},
        "location": {"country": "Germany"},
    }

    inputs = salary._collect_inputs(profile)
    result, explanation = salary._fallback_salary(inputs)

    assert result is not None
    assert result["salary_min"] == 65000.0
    assert result["salary_max"] == 90000.0
    assert result["currency"] == "EUR"
    assert isinstance(explanation, list)
    assert any(item.get("key") == "benchmark_role" for item in explanation)


def test_fallback_salary_includes_delta_details(monkeypatch) -> None:
    def fake_benchmark(role: str, country: str = "US") -> dict[str, str]:
        return {"salary_range": "80000-100000 USD"}

    monkeypatch.setattr(salary, "get_salary_benchmark", fake_benchmark)

    profile = {
        "position": {"job_title": "Software Developer"},
        "location": {"country": "Germany"},
        "compensation": {
            "salary_min": 90000,
            "salary_max": 105000,
            "currency": "EUR",
        },
    }

    inputs = salary._collect_inputs(profile)
    result, explanation = salary._fallback_salary(inputs)

    assert result is not None and result["currency"] == "USD"
    assert isinstance(explanation, list)

    min_entry = next(item for item in explanation if item.get("key") == "salary_min")
    impact = min_entry.get("impact")
    assert impact is not None
    assert impact.get("note") == "currency_mismatch"
    assert impact.get("user_currency") == "EUR"
    assert impact.get("user_value") == 90000.0
    assert impact.get("absolute") == pytest.approx(10000.0)
    assert impact.get("relative") == pytest.approx(0.125)

    max_entry = next(item for item in explanation if item.get("key") == "salary_max")
    impact_max = max_entry.get("impact")
    assert impact_max is not None
    assert impact_max.get("absolute") == pytest.approx(5000.0)


def test_call_salary_model_includes_city_and_skills(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_extraction_tool(*_args: object, **_kwargs: object) -> list[dict[str, object]]:
        return [{"type": "function", "function": {"name": "tool", "parameters": {}}}]

    class FakeResult:
        def __init__(self) -> None:
            self.tool_calls = [
                {
                    "function": {
                        "name": salary.FUNCTION_NAME,
                        "arguments": json.dumps(
                            {
                                "salary_min": 1,
                                "salary_max": 2,
                                "currency": "EUR",
                            }
                        ),
                        "input": json.dumps(
                            {
                                "salary_min": 1,
                                "salary_max": 2,
                                "currency": "EUR",
                            }
                        ),
                    }
                }
            ]
            self.content = ""

    def fake_call_chat_api(messages: list[dict[str, object]], **_kwargs: object) -> FakeResult:
        captured["messages"] = messages
        return FakeResult()

    monkeypatch.setattr(salary, "build_extraction_tool", fake_build_extraction_tool)
    monkeypatch.setattr(salary, "call_chat_api", fake_call_chat_api)

    inputs = salary._SalaryInputs(
        job_title="Product Manager",
        country="Germany",
        primary_city="Berlin",
        hq_location=None,
        seniority="Senior",
        work_policy="Hybrid",
        employment_type="Full-time",
        company_size="51-200",
        industry="Tech",
        current_min=70000.0,
        current_max=90000.0,
        current_currency="EUR",
        required_hard_skills=["Roadmapping"],
        required_soft_skills=["Communication"],
        hard_skills_optional=["SQL"],
        soft_skills_optional=["Coaching"],
        tools_and_technologies=["Jira"],
        certificates=["PMP"],
        languages_required=["English"],
        languages_optional=["German"],
        language_level_english="C1",
        core_responsibilities=["Own the roadmap"],
        must_have_requirements=["Roadmapping", "Communication"],
        nice_to_have_requirements=["SQL", "Coaching"],
        tools_tech_certificates=["Jira", "PMP"],
    )

    result, explanation = salary._call_salary_model(inputs)

    assert result is not None
    assert explanation is None

    messages = captured.get("messages")
    assert isinstance(messages, list) and len(messages) >= 2
    payload = json.loads(messages[1]["content"])

    assert payload["country"] == "Germany"
    assert payload["city"] == "Berlin"
    assert payload["core_responsibilities"] == ["Own the roadmap"]
    assert payload["must_have_requirements"] == ["Roadmapping", "Communication"]
    assert payload["nice_to_have_requirements"] == ["SQL", "Coaching"]
    assert payload["tools_tech_certificates"] == ["Jira", "PMP"]
    assert payload["tools_and_technologies"] == ["Jira"]
    assert payload["certificates"] == ["PMP"]
    assert payload["languages_required"] == ["English"]
    assert payload["languages_optional"] == ["German"]
    assert payload["language_level_english"] == "C1"
    assert "company_size" not in payload
