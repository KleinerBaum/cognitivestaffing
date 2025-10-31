from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


pytestmark = pytest.mark.integration


def test_salary_factor_entries(monkeypatch) -> None:
    sidebar_mod = import_module("sidebar.__init__")
    i18n_mod = import_module("utils.i18n")
    fake_state: dict[str, object] = {"lang": "de"}
    fake_streamlit = SimpleNamespace(session_state=fake_state)
    monkeypatch.setattr(sidebar_mod, "st", fake_streamlit)
    monkeypatch.setattr(i18n_mod, "st", fake_streamlit)

    explanation = [
        {"key": "source", "value": "Fallback", "impact": {"note": "fallback_source"}},
        {
            "key": "salary_min",
            "value": 60000.0,
            "impact": {
                "absolute": 5000.0,
                "relative": 0.0833,
                "user_value": 65000.0,
                "user_currency": "EUR",
            },
        },
    ]

    factors = sidebar_mod._prepare_salary_factors(
        explanation,
        benchmark_currency="EUR",
        user_currency="EUR",
    )

    assert factors[0].label == "Quelle"
    assert "Automatischer Fallback" in factors[0].impact_summary
    assert "Grund" in factors[0].explanation
    assert factors[1].label == "Unteres Benchmark-Ende"
    assert "+5·000 EUR" in factors[1].impact_summary
    assert "+5·000 EUR" in factors[1].explanation
    assert "verglichen mit deiner Eingabe" in factors[1].explanation
    assert factors[1].magnitude == 5000.0

    fake_state["lang"] = "en"
    factors_en = sidebar_mod._prepare_salary_factors(
        explanation,
        benchmark_currency="EUR",
        user_currency="EUR",
    )
    assert "Reason:" in factors_en[0].explanation
    assert "compared to your input 65·000 EUR" in factors_en[1].explanation
