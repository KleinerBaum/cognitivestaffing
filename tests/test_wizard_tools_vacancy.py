from __future__ import annotations

import json

import pytest

from wizard_tools import vacancy
from wizard.services.gaps import detect_missing_critical_fields
from wizard.services.validation import validate_profile


def test_upload_jobad_prefers_text_over_sources() -> None:
    payload = json.loads(vacancy.upload_jobad(source_url="https://example.com", file_id="file-1", text="Role"))

    assert payload == {"text": "Role", "metadata": {"source_url": "https://example.com", "file_id": "file-1"}}


def test_extract_vacancy_fields_infers_title_and_language() -> None:
    config = vacancy.ExtractionConfig(schema_version="v2", language="de", strict_json=False)
    payload = json.loads(vacancy.extract_vacancy_fields("Engineer\nBuild systems", config))

    assert payload["profile"] == {"title": "Engineer", "language": "de"}
    assert payload["schema_version"] == "v2"
    assert payload["strict_json"] is False
    assert payload["confidence"] == pytest.approx(0.9)


def test_extract_vacancy_fields_handles_empty_text() -> None:
    payload = json.loads(vacancy.extract_vacancy_fields("", vacancy.ExtractionConfig()))

    assert payload["profile"]["title"] == "Untitled role"
    assert payload["confidence"] == pytest.approx(0.5)


def test_detect_gaps_and_followups_cover_missing_fields() -> None:
    profile = {"requirements": {}}
    gaps = json.loads(vacancy.detect_gaps(profile))["gaps"]
    fields = [entry["field"] for entry in gaps]
    service_fields = detect_missing_critical_fields(profile)
    assert fields == service_fields
    assert {"position.job_title", "requirements.hard_skills_required"}.issubset(fields)

    followups = json.loads(vacancy.generate_followups(profile, role_context="remote team"))
    assert any("role context" in question for question in followups["questions"])


def test_ingest_answers_merges_payload() -> None:
    answers = [{"question": "Q", "answer": "A"}]
    profile: dict[str, object] = {"position": {"job_title": "Engineer"}}
    merged = json.loads(vacancy.ingest_answers(answers, profile))

    assert merged["profile"]["answers"] == answers


def test_validate_profile_reports_issues() -> None:
    config = vacancy.ValidationConfig(jurisdiction="DE", constraints=None)
    profile = {"compensation": {"salary": {"min": 100000, "max": 90000}}}
    result = json.loads(vacancy.validate_profile(profile, config))

    service_result = validate_profile(profile, jurisdiction="DE")

    assert result["ok"] is False
    assert result["issues"] == service_result.issues
    assert result["missing_required"] == service_result.missing_required
    assert any("Location is required" in issue for issue in result["issues"])
    assert "Salary minimum cannot exceed maximum." in result["issues"]


def test_map_esco_skills_and_salary_enrichment() -> None:
    profile = {"requirements": {"hard_skills_required": ["Python", " "]}, "position": {"seniority": "Senior"}}
    skills = json.loads(vacancy.map_esco_skills(profile))["skills"]
    assert skills == [{"name": "Python", "level": "advanced"}]

    salary = json.loads(vacancy.market_salary_enrich(profile, "DE"))["salary"]
    assert salary["region"] == "DE"
    assert salary["min"] == 85000
    assert salary["max"] == 120000


def test_generate_jd_and_export_profile() -> None:
    profile = {
        "company": {"name": "Cognitive Staffing"},
        "position": {"job_title": "AI Engineer"},
    }
    drafts = json.loads(vacancy.generate_jd(profile, tone="exciting", lang="en"))["drafts"]
    assert any("Cognitive Staffing" in draft["text"] for draft in drafts)
    assert {draft["kind"] for draft in drafts} == {"short", "long"}

    export = json.loads(vacancy.export_profile(profile, format="md"))
    assert export == {
        "file_url": "https://files/export/profile.md",
        "format": "md",
        "preview": "AI Engineer",
    }
