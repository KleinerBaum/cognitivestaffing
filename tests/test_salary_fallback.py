from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
