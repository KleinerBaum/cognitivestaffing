from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace


def test_salary_factor_table_formatting(monkeypatch) -> None:
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

    rows = sidebar_mod._prepare_salary_factor_rows(
        explanation,
        benchmark_currency="EUR",
        user_currency="EUR",
    )

    assert rows[0][0] == "Quelle"
    table = sidebar_mod._build_salary_factor_table(rows)
    assert "| Quelle |" in table
    assert "+5·000 EUR" in table
    assert "vs. Eingabe 65·000 EUR" in table

    fake_state["lang"] = "en"
    rows_en = sidebar_mod._prepare_salary_factor_rows(
        explanation,
        benchmark_currency="EUR",
        user_currency="EUR",
    )
    table_en = sidebar_mod._build_salary_factor_table(rows_en)
    assert "| Factor |" in table_en
    assert "vs. input 65·000 EUR" in table_en
