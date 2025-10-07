import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.job_ad import resolve_job_ad_field_selection


def test_resolve_job_ad_field_selection_filters_unavailable_keys():
    available_keys = {
        "position.job_title",
        "company.name",
        "employment.job_type",
    }
    selected_keys = {
        "company.name",
        "employment.job_type",
        "requirements.hard_skills_required",
    }

    result = resolve_job_ad_field_selection(available_keys, selected_keys)

    assert result == ["company.name", "employment.job_type"]


def test_resolve_job_ad_field_selection_defaults_to_available_when_none():
    available_keys = ["position.job_title", "company.name"]

    result = resolve_job_ad_field_selection(available_keys, None)

    assert result == ["position.job_title", "company.name"]
