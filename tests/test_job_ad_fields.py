from __future__ import annotations

from collections.abc import Mapping

from core.job_ad import JOB_AD_FIELDS
from wizard import _job_ad_field_entries, _prepare_job_ad_data


def _field_by_key(key: str):
    return next(field for field in JOB_AD_FIELDS if field.key == key)


def test_job_ad_field_entries_include_benefits() -> None:
    data: Mapping[str, object] = {"compensation": {"benefits": ["Gym", "gym", "Health Insurance"]}}

    entries = _job_ad_field_entries(data, _field_by_key("compensation.benefits"), "en")

    assert [label for _, label in entries] == ["Gym", "Health Insurance"]


def test_job_ad_field_entries_include_work_policy_details() -> None:
    data: Mapping[str, object] = {"employment": {"work_policy": "remote", "remote_percentage": 60}}

    entries = _job_ad_field_entries(data, _field_by_key("employment.work_policy"), "en")

    assert entries == [("employment.work_policy::0", "remote (60% remote)")]


def test_prepare_job_ad_data_sanitizes_legacy_keys() -> None:
    payload: Mapping[str, object] = {
        "company": {"name": "Example"},
        "location": {"city": "Berlin"},
        "employment": {"work_model": "hybrid"},
        "compensation": {"benefits": ["Gym"]},
    }

    sanitized = _prepare_job_ad_data(payload)

    assert sanitized["location"]["primary_city"] == "Berlin"
    assert "city" not in sanitized["location"]
    assert sanitized["employment"]["work_policy"] == "hybrid"
    assert "work_model" not in sanitized["employment"]
    assert sanitized["compensation"]["benefits"] == ["Gym"]
