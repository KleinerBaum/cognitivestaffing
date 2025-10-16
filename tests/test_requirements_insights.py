from __future__ import annotations

from components.requirements_insights import (
    build_availability_chart_spec,
    build_salary_chart_spec,
    prepare_skill_market_records,
)


def _sample_dataset() -> dict[str, dict[str, object]]:
    return {
        "python": {
            "aliases": ["python"],
            "salary_delta_pct": 6.0,
            "availability_index": 44.0,
            "regions": {
                "berlin de": [
                    {
                        "max_radius": 30,
                        "salary_delta_pct": 7.2,
                        "availability_index": 39.0,
                    },
                    {
                        "salary_delta_pct": 6.3,
                        "availability_index": 42.0,
                    },
                ]
            },
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


def test_prepare_skill_market_records_respects_radius_location() -> None:
    dataset = _sample_dataset()
    location = {"primary_city": "Berlin", "country": "DE"}
    records = prepare_skill_market_records(
        ["Python"],
        dataset=dataset,
        location=location,
        radius_km=25,
    )
    assert len(records) == 1
    entry = records[0]
    assert entry.salary_delta_pct == 7.2
    assert entry.availability_index == 39.0
    assert entry.region_label == "Berlin DE"


def test_chart_specs_update_when_skills_change() -> None:
    dataset = _sample_dataset()
    python_records = prepare_skill_market_records(["Python"], dataset=dataset)
    java_records = prepare_skill_market_records(["Java"], dataset=dataset)

    python_salary_spec = build_salary_chart_spec(python_records, lang="de")
    java_salary_spec = build_salary_chart_spec(java_records, lang="de")
    python_availability_spec = build_availability_chart_spec(python_records, lang="de")
    java_availability_spec = build_availability_chart_spec(java_records, lang="de")

    assert python_salary_spec["data"]["values"] != java_salary_spec["data"]["values"], (
        "Salary chart should change when the skill selection changes."
    )
    assert python_availability_spec["data"]["values"] != java_availability_spec["data"]["values"], (
        "Availability chart should change when the skill selection changes."
    )
