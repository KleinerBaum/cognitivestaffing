from __future__ import annotations

import json
from pathlib import Path

import pytest

from wizard_tools import vacancy
from ingest.types import ContentBlock, StructuredDocument
from wizard.services.gaps import detect_missing_critical_fields
from wizard.services.validation import validate_profile


def test_upload_jobad_prefers_text_over_sources() -> None:
    payload = json.loads(vacancy.upload_jobad(source_url="https://example.com", file_id="file-1", text="Role"))

    assert payload["text"] == "Role"
    assert payload["metadata"]["source_url"] == "https://example.com"
    assert payload["metadata"]["file_id"] == "file-1"
    assert payload["metadata"]["source_kind"] == "text"


def test_upload_jobad_reads_url_via_ingestion(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = StructuredDocument(
        text="Line A\n\nLine B",
        blocks=[ContentBlock(type="paragraph", text="Line A"), ContentBlock(type="paragraph", text="Line B")],
        source="https://example.com/job",
    )
    monkeypatch.setattr(vacancy, "extract_text_from_url", lambda _url: expected)

    payload = json.loads(vacancy.upload_jobad(source_url="https://example.com/job"))

    assert payload["text"] == "Line A\n\nLine B"
    assert payload["metadata"]["source_kind"] == "url"
    assert payload["metadata"]["block_count"] == 2


def test_upload_jobad_reads_file_via_ingestion(tmp_path: Path) -> None:
    path = tmp_path / "job.txt"
    path.write_text("Engineer\n\nTasks", encoding="utf-8")

    payload = json.loads(vacancy.upload_jobad(file_id=str(path)))

    assert payload["text"] == "Engineer\nTasks"
    assert payload["metadata"]["source_kind"] == "file"


def test_upload_jobad_rejects_missing_file() -> None:
    with pytest.raises(ValueError, match="existing local file path"):
        vacancy.upload_jobad(file_id="/tmp/does-not-exist.txt")


def test_extract_vacancy_fields_uses_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_extract(text: str):
        assert text == "Engineer\nBuild systems"
        return type(
            "_Result",
            (),
            {
                "data": {"position": {"job_title": "Engineer"}},
                "recovered": True,
                "issues": ["example_issue"],
                "low_confidence": False,
                "repair_applied": True,
                "repair_count": 1,
                "missing_required_count": 2,
                "degraded": True,
                "degraded_reasons": ["missing_required_fields_after_retry"],
            },
        )()

    monkeypatch.setattr(vacancy, "extract_need_analysis_profile", _fake_extract)

    config = vacancy.ExtractionConfig(schema_version="v2", strict_json=False)
    payload = json.loads(vacancy.extract_vacancy_fields("Engineer\nBuild systems", config))

    assert payload["profile"]["position"]["job_title"] == "Engineer"
    assert payload["schema_version"] == "v2"
    assert payload["strict_json"] is False
    assert payload["recovered"] is True
    assert payload["issues"] == ["example_issue"]


def test_extract_vacancy_fields_handles_empty_text() -> None:
    payload = json.loads(vacancy.extract_vacancy_fields("", vacancy.ExtractionConfig()))

    assert payload["issues"] == ["empty_input_text"]
    assert payload["degraded"] is True
    assert payload["profile"]["position"]["job_title"] is None


def test_detect_gaps_and_followups_cover_missing_fields() -> None:
    profile = {"requirements": {}}
    gaps = json.loads(vacancy.detect_gaps(profile))["gaps"]
    fields = [entry["field"] for entry in gaps]
    service_fields = detect_missing_critical_fields(profile)
    assert fields == service_fields
    assert {"position.job_title", "requirements.hard_skills_required"}.issubset(fields)

    followups = json.loads(vacancy.generate_followups(profile, role_context="remote team"))
    assert any(
        "remote team" in entry.get("question", "")
        for entry in followups.get("questions", [])
        if isinstance(entry, dict)
    )


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
    profile = {
        "requirements": {"hard_skills_required": ["Python", " "]},
        "position": {"job_title": "Senior Data Engineer"},
    }
    skills = json.loads(vacancy.map_esco_skills(profile))["skills"]
    assert skills == [{"name": "Python", "level": "advanced"}]

    salary = json.loads(vacancy.market_salary_enrich(profile, "DE"))["salary"]
    assert salary["region"] == "DE"
    assert salary["min"] == 76000
    assert salary["max"] == 105000
    assert salary["currency"] == "EUR"
    assert salary["degraded"] is False


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
