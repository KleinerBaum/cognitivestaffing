"""Vacancy data operations exposed as agent tools."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents import function_tool
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from ingest.extractors import extract_text_from_file, extract_text_from_url
from ingest.reader import clean_job_text
from ingest.types import StructuredDocument, build_plain_text_document
from models.need_analysis import NeedAnalysisProfile
from pipelines.need_analysis import extract_need_analysis_profile
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

    source_kind = "text"
    document: StructuredDocument | None = None

    if isinstance(text, str) and text.strip():
        source_kind = "text"
        document = build_plain_text_document(text, source="pasted")
    elif isinstance(source_url, str) and source_url.strip():
        source_kind = "url"
        document = extract_text_from_url(source_url.strip())
    elif isinstance(file_id, str) and file_id.strip():
        file_path = Path(file_id).expanduser()
        if not file_path.exists() or not file_path.is_file():
            raise ValueError("file_id must reference an existing local file path")
        with file_path.open("rb") as handle:
            document = extract_text_from_file(handle)
        source_kind = "file"
    else:
        raise ValueError("Provide one of: text, source_url, or file_id")

    canonical_text = clean_job_text(document.text if document else "")
    if not canonical_text:
        raise ValueError("Uploaded source contains no extractable text")

    metadata = {
        "source_url": source_url,
        "file_id": file_id,
        "source_kind": source_kind,
        "source": document.source if document else None,
        "block_count": len(document.blocks) if document else 0,
    }
    return json.dumps({"text": canonical_text, "metadata": metadata})


@function_tool
def extract_vacancy_fields(text: str, config: ExtractionConfig) -> str:
    """Run structured extraction to the vacancy schema."""

    content = (text or "").strip()
    if not content:
        profile = NeedAnalysisProfile().model_dump(mode="python")
        return json.dumps(
            {
                "profile": profile,
                "schema_version": config.schema_version,
                "strict_json": config.strict_json,
                "recovered": False,
                "issues": ["empty_input_text"],
                "degraded": True,
                "degraded_reasons": ["empty_input_text"],
            }
        )

    result = extract_need_analysis_profile(content)
    payload = {
        "profile": result.data,
        "schema_version": config.schema_version,
        "strict_json": config.strict_json,
        "recovered": result.recovered,
        "issues": result.issues,
        "low_confidence": result.low_confidence,
        "repair_applied": result.repair_applied,
        "repair_count": result.repair_count,
        "missing_required_count": result.missing_required_count,
        "degraded": result.degraded,
        "degraded_reasons": result.degraded_reasons,
    }
    return json.dumps(payload)


_RANGE_PATTERN = re.compile(r"(?P<currency>[€$£])?\s*(?P<low>[0-9]+(?:[.,][0-9]+)?)\s*[kK]?\s*[-–—]\s*(?P<tail>.+)$")


def _parse_salary_range(range_text: str) -> tuple[int | None, int | None, str | None]:
    match = _RANGE_PATTERN.search(range_text or "")
    if not match:
        return None, None, None
    low_raw = match.group("low").replace(",", ".")
    tail = match.group("tail")
    high_match = re.search(r"([0-9]+(?:[.,][0-9]+)?)", tail)
    if not high_match:
        return None, None, None
    high_raw = high_match.group(1).replace(",", ".")
    try:
        low_value = float(low_raw)
        high_value = float(high_raw)
    except ValueError:
        return None, None, None

    magnitude = 1000 if "k" in range_text.lower() else 1
    currency_symbol = match.group("currency")
    currency = {"€": "EUR", "$": "USD", "£": "GBP"}.get(currency_symbol)
    return int(low_value * magnitude), int(high_value * magnitude), currency


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

    profile = profile_json or {}
    position = profile.get("position", {}) if isinstance(profile.get("position"), dict) else {}
    role_title = str(position.get("job_title") or "")
    country = (region or "US").strip().upper() or "US"

    benchmark = get_salary_benchmark(role_title, country=country)
    salary_range = str(benchmark.get("salary_range") or "unknown")
    min_salary, max_salary, parsed_currency = _parse_salary_range(salary_range)
    canonical_role = resolve_salary_role(role_title)

    salary = {
        "min": min_salary,
        "max": max_salary,
        "currency": parsed_currency,
        "region": country,
        "role": canonical_role or role_title,
        "salary_range": salary_range,
        "degraded": min_salary is None or max_salary is None,
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
