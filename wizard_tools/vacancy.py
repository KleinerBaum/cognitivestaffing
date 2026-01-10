"""Vacancy data operations exposed as agent tools."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents import function_tool
from wizard.services.followups import FollowupModelConfig, generate_followups as generate_followups_service
from wizard.services.gaps import detect_missing_critical_fields
from wizard.services.job_description import generate_job_description
from wizard.services.validation import validate_profile as validate_profile_service


class ExtractionConfig(BaseModel):
    schema_version: str = "v1"
    language: Optional[str] = None
    strict_json: bool = True


class ValidationConfig(BaseModel):
    jurisdiction: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None


@function_tool
def upload_jobad(
    source_url: Optional[str] = None,
    file_id: Optional[str] = None,
    text: Optional[str] = None,
) -> str:
    """Normalise a job ad into text + metadata."""

    norm_text = text or f"// fetched from {source_url or file_id}"
    return json.dumps({"text": norm_text, "metadata": {"source_url": source_url, "file_id": file_id}})


@function_tool
def extract_vacancy_fields(text: str, config: ExtractionConfig) -> str:
    """Run structured extraction to the vacancy schema."""

    content = (text or "").strip()
    title = content.splitlines()[0].strip() if content else "Untitled role"
    profile: dict[str, Any] = {"title": title}
    if config.language:
        profile["language"] = config.language
    payload = {
        "profile": profile,
        "confidence": 0.9 if content else 0.5,
        "schema_version": config.schema_version,
        "strict_json": config.strict_json,
    }
    return json.dumps(payload)


@function_tool
def detect_gaps(profile_json: Dict[str, Any]) -> str:
    """Return list of missing/ambiguous fields."""

    profile = profile_json or {}
    missing_fields = detect_missing_critical_fields(profile)
    gaps = [{"field": field, "reason": "missing"} for field in missing_fields]
    return json.dumps({"gaps": gaps})


@function_tool
def generate_followups(profile_json: Dict[str, Any], role_context: Optional[str] = None) -> str:
    """Produce prioritised follow-up questions for SMEs."""

    profile = profile_json or {}
    locale = str(profile.get("meta", {}).get("lang") or profile.get("language") or "en")
    result = generate_followups_service(
        profile,
        mode="fast",
        locale=locale,
        model_config=FollowupModelConfig(),
        role_context=role_context,
    )
    return json.dumps(result)


@function_tool
def ingest_answers(qa_pairs: List[Dict[str, str]], profile_json: Dict[str, Any]) -> str:
    """Merge SME answers into the profile."""

    profile_json["answers"] = qa_pairs
    return json.dumps({"profile": profile_json})


@function_tool
def validate_profile(profile_json: Dict[str, Any], config: ValidationConfig) -> str:
    """Validate profile (comp bands, location, legal)."""

    profile = profile_json or {}
    result = validate_profile_service(profile, jurisdiction=config.jurisdiction)
    return json.dumps({"ok": result.ok, "issues": result.issues, "missing_required": result.missing_required})


@function_tool
def map_esco_skills(profile_json: Dict[str, Any]) -> str:
    """Map skills to ESCO taxonomy with levels."""

    requirements = (profile_json or {}).get("requirements", {})
    skills = [
        {"name": skill, "level": "advanced"}
        for skill in requirements.get("hard_skills_required", [])
        if isinstance(skill, str) and skill.strip()
    ]
    return json.dumps({"skills": skills})


@function_tool
def market_salary_enrich(profile_json: Dict[str, Any], region: str) -> str:
    """Attach market salary ranges + rationale."""

    seniority = (profile_json or {}).get("position", {}).get("seniority", "mid").lower()
    base_min, base_max = {
        "junior": (42000, 60000),
        "mid": (60000, 90000),
        "senior": (85000, 120000),
    }.get(seniority, (60000, 90000))
    salary = {
        "min": base_min,
        "max": base_max,
        "currency": "EUR",
        "region": region,
        "seniority": seniority,
    }
    return json.dumps({"salary": salary})


@function_tool
def generate_jd(profile_json: Dict[str, Any], tone: str = "professional", lang: str = "en") -> str:
    """Generate Job Description variants."""

    result = generate_job_description(profile_json or {}, tone=tone, lang=lang)
    return json.dumps(result)


@function_tool
def export_profile(profile_json: Dict[str, Any], format: str = "json") -> str:
    """Export the profile in a given format."""

    preview = (profile_json or {}).get("position", {}).get("job_title")
    return json.dumps(
        {
            "file_url": f"https://files/export/profile.{format}",
            "format": format,
            "preview": preview,
        }
    )


__all__ = [
    "ExtractionConfig",
    "ValidationConfig",
    "detect_gaps",
    "export_profile",
    "generate_followups",
    "generate_jd",
    "ingest_answers",
    "map_esco_skills",
    "market_salary_enrich",
    "extract_vacancy_fields",
    "upload_jobad",
    "validate_profile",
]
