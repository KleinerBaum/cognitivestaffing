"""
Vacalyzer – canonical extraction schema and coercion utilities.
"""
from __future__ import annotations
from typing import Any, Dict, Iterable, List

# --- Pydantic v2/v1 compatibility ---
try:
    from pydantic import BaseModel, Field  # type: ignore
    from pydantic import ConfigDict  # v2 compatibility
    _HAS_V2 = True
except Exception:
    from pydantic import BaseModel, Field  # type: ignore
    ConfigDict = None
    _HAS_V2 = False

SCHEMA_VERSION = "v1.0"

# Ordered canonical list of schema keys (excluding schema_version).
# Keep this list authoritative for prompts, validation, and UI wiring.
ALL_FIELDS: List[str] = [
    "job_title",
    "company_name",
    "location",
    "industry",
    "job_type",
    "remote_policy",
    "travel_required",
    "role_summary",
    "responsibilities",
    "hard_skills",
    "soft_skills",
    "qualifications",
    "certifications",
    "salary_range",
    "benefits",
    "reporting_line",
    "target_start_date",
    "team_structure",
    "application_deadline",
    "seniority_level",
    "languages_required",
    "tools_and_technologies",
]
# Ensure the schema contains the expected number of fields
assert len(ALL_FIELDS) == 22, "ALL_FIELDS must contain 22 keys."

# List-typed fields in the schema.
LIST_FIELDS = {
    "responsibilities",
    "hard_skills",
    "soft_skills",
    "certifications",
    "benefits",
    "languages_required",
    "tools_and_technologies",
}

# Convenience set of string-typed fields.
STRING_FIELDS = set(ALL_FIELDS) - set(LIST_FIELDS)

# Backward-compatibility aliases (input normalization only).
ALIASES: Dict[str, str] = {
    "requirements": "qualifications",
    "contract_type": "job_type",
    "tasks": "responsibilities",
    "experience_level": "seniority_level",
    "start_date": "target_start_date",
    "tools_technologies": "tools_and_technologies",
}

# Base model configuration for extra fields
if _HAS_V2:
    class _BaseModel(BaseModel):
        model_config = ConfigDict(extra="ignore")
else:  # Pydantic v1
    class _BaseModel(BaseModel):
        class Config:
            extra = "ignore"

class VacalyserJD(_BaseModel):
    """
    Canonical job description model (vacancy profile). All string fields default to "",
    all list fields default to []. Always include every key (even if empty) to keep the shape stable.
    """
    schema_version: str = Field(default=SCHEMA_VERSION)
    # String fields
    job_title: str = ""
    company_name: str = ""
    location: str = ""
    industry: str = ""
    job_type: str = ""
    remote_policy: str = ""
    travel_required: str = ""
    role_summary: str = ""
    qualifications: str = ""
    salary_range: str = ""
    reporting_line: str = ""
    target_start_date: str = ""
    team_structure: str = ""
    application_deadline: str = ""
    seniority_level: str = ""
    # List fields
    responsibilities: List[str] = []
    hard_skills: List[str] = []
    soft_skills: List[str] = []
    certifications: List[str] = []
    benefits: List[str] = []
    languages_required: List[str] = []
    tools_and_technologies: List[str] = []

def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    """Remove duplicates from a list while preserving order and stripping whitespace."""
    seen = set()
    out: List[str] = []
    for x in items:
        val = str(x).strip()
        if not val:
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out

def coerce_and_fill(data: Dict[str, Any]) -> VacalyserJD:
    """
    Normalize an arbitrary dict into a validated VacalyserJD.
    Steps:
      1) Apply alias mapping (e.g., "tasks" -> "responsibilities").
      2) Insert any missing keys ('' for strings, [] for lists).
      3) Coerce list fields to List[str], splitting strings by common delimiters, and deduplicate.
      4) Coerce string fields to str and strip whitespace.
      5) Ignore unknown extra keys.
    """
    if data is None:
        data = {}
    # 1) apply aliases
    for old, new in ALIASES.items():
        if old in data and new not in data:
            data[new] = data.pop(old)
    # 2) insert missing keys with defaults
    for key in ALL_FIELDS:
        if key not in data:
            data[key] = [] if key in LIST_FIELDS else ""
    # 3) coerce list fields
    for key in LIST_FIELDS:
        value = data.get(key, [])
        if isinstance(value, str):
            # Split on newlines and commas/semicolons for list fields
            parts: List[str] = []
            for chunk in value.replace("\r\n", "\n").split("\n"):
                parts.extend(chunk.split(","))
            value = parts
        elif not isinstance(value, list):
            value = [value]
        data[key] = _dedupe_preserve_order(value)
    # 4) coerce string fields
    for key in STRING_FIELDS:
        val = data.get(key, "")
        if val is None:
            val = ""
        data[key] = str(val).strip()
    # 5) build model (extra keys ignored by BaseModel config)
    return VacalyserJD(**data)
