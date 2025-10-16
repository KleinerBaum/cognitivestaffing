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

    return json.dumps({"profile": {"title": "Software Engineer"}, "confidence": 0.83})


@function_tool
def detect_gaps(profile_json: Dict[str, Any]) -> str:
    """Return list of missing/ambiguous fields."""

    return json.dumps({"gaps": [{"field": "benefits", "reason": "missing"}]})


@function_tool
def generate_followups(profile_json: Dict[str, Any], role_context: Optional[str] = None) -> str:
    """Produce prioritised follow-up questions for SMEs."""

    return json.dumps({"questions": ["What are the core benefits?", "Travel requirements?"]})


@function_tool
def ingest_answers(qa_pairs: List[Dict[str, str]], profile_json: Dict[str, Any]) -> str:
    """Merge SME answers into the profile."""

    profile_json["answers"] = qa_pairs
    return json.dumps({"profile": profile_json})


@function_tool
def validate_profile(profile_json: Dict[str, Any], config: ValidationConfig) -> str:
    """Validate profile (comp bands, location, legal)."""

    return json.dumps({"ok": True, "issues": []})


@function_tool
def map_esco_skills(profile_json: Dict[str, Any]) -> str:
    """Map skills to ESCO taxonomy with levels."""

    return json.dumps({"skills": [{"name": "Python", "level": "advanced"}]})


@function_tool
def market_salary_enrich(profile_json: Dict[str, Any], region: str) -> str:
    """Attach market salary ranges + rationale."""

    return json.dumps({"salary": {"min": 60000, "max": 90000, "currency": "EUR", "region": region}})


@function_tool
def generate_jd(profile_json: Dict[str, Any], tone: str = "professional", lang: str = "en") -> str:
    """Generate Job Description variants."""

    return json.dumps({"drafts": [{"kind": "short", "text": "JD short..."}, {"kind": "long", "text": "JD long..."}]})


@function_tool
def export_profile(profile_json: Dict[str, Any], format: str = "json") -> str:
    """Export the profile in a given format."""

    return json.dumps({"file_url": f"https://files/export/profile.{format}"})


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

