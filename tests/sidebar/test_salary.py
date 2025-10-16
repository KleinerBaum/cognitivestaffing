from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


salary = import_module("sidebar.salary")


def test_collect_inputs_includes_extended_requirements() -> None:
    profile = {
        "position": {"job_title": "Data Scientist"},
        "location": {"country": "Germany"},
        "requirements": {
            "hard_skills_required": ["Python"],
            "soft_skills_required": ["Teamwork"],
            "hard_skills_optional": ["Scala"],
            "soft_skills_optional": ["Facilitation"],
            "tools_and_technologies": ["TensorFlow", "Docker"],
            "certifications": ["AWS ML Specialty"],
            "languages_required": ["English", "German"],
            "languages_optional": ["French"],
            "language_level_english": "C1",
        },
    }

    inputs = salary._collect_inputs(profile)

    assert inputs.hard_skills_optional == ["Scala"]
    assert inputs.soft_skills_optional == ["Facilitation"]
    assert inputs.tools_and_technologies == ["TensorFlow", "Docker"]
    assert inputs.certificates == ["AWS ML Specialty"]
    assert inputs.languages_required == ["English", "German"]
    assert inputs.languages_optional == ["French"]
    assert inputs.language_level_english == "C1"


def test_fallback_salary_applies_adjustments(monkeypatch) -> None:
    def fake_benchmark(role: str, country: str = "US") -> dict[str, str]:
        return {"salary_range": "40000-50000"}

    monkeypatch.setattr(salary, "get_salary_benchmark", fake_benchmark)

    profile = {
        "position": {"job_title": "AI Engineer"},
        "location": {"country": "Germany"},
        "requirements": {
            "hard_skills_required": ["Python", "Machine Learning"],
            "soft_skills_required": ["Communication"],
            "hard_skills_optional": ["Scala", "Go"],
            "soft_skills_optional": ["Stakeholder Management"],
            "tools_and_technologies": ["TensorFlow", "Kubernetes"],
            "certificates": ["AWS ML Specialty"],
            "languages_required": ["English", "German"],
            "languages_optional": ["French"],
            "language_level_english": "C1",
        },
    }

    inputs = salary._collect_inputs(profile)
    result, explanation = salary._fallback_salary(inputs)

    assert result is not None
    assert result["salary_min"] == 47200.0
    assert result["salary_max"] == 59000.0
    assert "Zertifikate" in explanation
    assert "Englischniveau" in explanation
