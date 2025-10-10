from __future__ import annotations

from components.requirements_insights import (
    build_skill_market_chart_spec,
    prepare_skill_market_records,
)


def _sample_dataset() -> dict[str, dict[str, object]]:
    return {
        "python": {
            "aliases": ["python"],
            "salary_delta_pct": 6.0,
            "availability_index": 44.0,
        },
        "java": {
            "aliases": ["java"],
            "salary_delta_pct": 4.0,
            "availability_index": 52.0,
        },
        "english": {
            "aliases": ["english", "englisch"],
            "salary_delta_pct": 0.0,
            "availability_index": 80.0,
        },
    }


def test_prepare_skill_market_records_uses_fallback_for_unknown_skill() -> None:
    dataset = _sample_dataset()
    records = prepare_skill_market_records(["Unicorn Handling"], dataset=dataset)
    assert len(records) == 1
    fallback = records[0]
    assert fallback.has_benchmark is False
    assert fallback.salary_delta_pct == 0.0
    assert fallback.availability_index == 50.0


def test_prepare_skill_market_records_matches_language_variants() -> None:
    dataset = _sample_dataset()
    records = prepare_skill_market_records(["English (C1)"], dataset=dataset)
    assert len(records) == 1
    entry = records[0]
    assert entry.has_benchmark is True
    assert entry.salary_delta_pct == 0.0
    assert entry.availability_index == 80.0


def test_chart_spec_updates_when_skills_change() -> None:
    dataset = _sample_dataset()
    python_records = prepare_skill_market_records(["Python"], dataset=dataset)
    java_records = prepare_skill_market_records(["Java"], dataset=dataset)

    python_spec = build_skill_market_chart_spec(python_records, lang="de")
    java_spec = build_skill_market_chart_spec(java_records, lang="de")

    assert python_spec["data"]["values"] != java_spec["data"]["values"], (
        "The visualization spec should reflect different skill inputs."
    )
