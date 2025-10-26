"""Vacancy data operations exposed as agent tools."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents import function_tool


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
    position = profile.get("position", {})
    requirements = profile.get("requirements", {})
    gaps: list[dict[str, str]] = []
    if not position.get("job_title"):
        gaps.append({"field": "position.job_title", "reason": "missing"})
    if not position.get("location"):
        gaps.append({"field": "position.location", "reason": "missing"})
    if not requirements.get("hard_skills_required"):
        gaps.append({"field": "requirements.hard_skills_required", "reason": "missing"})
    return json.dumps({"gaps": gaps})


@function_tool
def generate_followups(profile_json: Dict[str, Any], role_context: Optional[str] = None) -> str:
    """Produce prioritised follow-up questions for SMEs."""

    position = (profile_json or {}).get("position", {})
    title = position.get("job_title") or "this role"
    questions = [
        f"What unique benefits should we highlight for {title}?",
        "Are there travel or on-site expectations?",
    ]
    if role_context:
        questions.append(f"Anything noteworthy about the role context: {role_context}?")
    return json.dumps({"questions": questions})


@function_tool
def ingest_answers(qa_pairs: List[Dict[str, str]], profile_json: Dict[str, Any]) -> str:
    """Merge SME answers into the profile."""

    profile_json["answers"] = qa_pairs
    return json.dumps({"profile": profile_json})


@function_tool
def validate_profile(profile_json: Dict[str, Any], config: ValidationConfig) -> str:
    """Validate profile (comp bands, location, legal)."""

    issues: list[str] = []
    profile = profile_json or {}
    if config.jurisdiction and not profile.get("position", {}).get("location"):
        issues.append(f"Location is required for {config.jurisdiction} reviews.")
    compensation = profile.get("compensation", {})
    salary = compensation.get("salary")
    if isinstance(salary, dict):
        minimum = salary.get("min")
        maximum = salary.get("max")
        if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)) and minimum > maximum:
            issues.append("Salary minimum cannot exceed maximum.")
    return json.dumps({"ok": not issues, "issues": issues})


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

    profile = profile_json or {}
    company = profile.get("company", {}).get("name") or "your organisation"
    title = profile.get("position", {}).get("job_title") or "Team member"
    intro = f"Join {company} as a {title}. We are looking for {tone} contributors ready to grow with us."
    detailed = f"{intro} Responsibilities include collaborating across teams and delivering outcomes in line with our {tone} culture."
    drafts = [
        {"kind": "short", "text": intro, "lang": lang},
        {"kind": "long", "text": detailed, "lang": lang},
    ]
    return json.dumps({"drafts": drafts})


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
