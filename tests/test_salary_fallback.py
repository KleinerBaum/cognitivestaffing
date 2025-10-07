from __future__ import annotations

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


def test_us_state_abbreviation_does_not_trigger_wrong_country() -> None:
    country = salary._derive_country_from_locations("San Jose, CA")
    assert country == "United States"


def test_canadian_city_with_abbreviation_maps_to_canada() -> None:
    country = salary._derive_country_from_locations("Toronto, CA")
    assert country == "Canada"
