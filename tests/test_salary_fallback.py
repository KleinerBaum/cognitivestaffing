from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
import sys
from types import SimpleNamespace


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
    assert explanation is not None and "fallback" in explanation.lower()


def test_estimate_uses_city_when_country_missing(monkeypatch) -> None:
    monkeypatch.setattr(salary, "call_chat_api", None)
    monkeypatch.setattr(salary, "build_extraction_tool", None)

    fake_state: dict[str, object] = {}
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
    assert explanation is not None


def test_call_salary_model_includes_city_and_skills(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_build_extraction_tool(*_args: object, **_kwargs: object) -> dict[str, str]:
        return {"name": "tool"}

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
    )

    result, explanation = salary._call_salary_model(inputs)

    assert result is not None
    assert explanation is None

    messages = captured.get("messages")
    assert isinstance(messages, list) and len(messages) >= 2
    payload = json.loads(messages[1]["content"])

    assert payload["primary_city"] == "Berlin"
    assert payload["required_hard_skills"] == ["Roadmapping"]
    assert payload["required_soft_skills"] == ["Communication"]
