"""
Vacalyzer – canonical extraction schema and coercion utilities.
"""

from __future__ import annotations
import re
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
    # role-specific list fields
    "programming_languages",
    "frameworks",
    "tech_stack",
    "code_quality_practices",
    "target_markets",
    "crm_tools",
    "campaign_types",
    "digital_marketing_platforms",
    "required_certifications",
    "design_software_tools",
    "project_management_methodologies",
    "project_management_tools",
    "stakeholder_types",
    "machine_learning_frameworks",
    "data_analysis_tools",
    "data_visualization_tools",
    "accounting_software",
    "professional_certifications",
    "reporting_standards",
    "regulatory_frameworks",
    "hr_software_tools",
    "recruitment_channels",
    "employee_engagement_strategies",
    "engineering_software_tools",
    "civil_project_types",
    "cuisine_specialties",
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

# Canonical category mappings.
JOB_TYPE_CATEGORIES: Dict[str, str] = {
    "full-time": "Full-time",
    "full time": "Full-time",
    "fulltime": "Full-time",
    "part-time": "Part-time",
    "part time": "Part-time",
    "parttime": "Part-time",
    "contract": "Contract",
    "contractor": "Contract",
    "temporary": "Temporary",
    "temp": "Temporary",
    "internship": "Internship",
    "intern": "Internship",
}


def _normalize_job_type(value: str) -> str:
    """Normalize job type string to a canonical category.

    Args:
        value: Raw job type value.

    Returns:
        Canonical job type with standardized capitalization.

    Raises:
        ValueError: If the value does not map to a known category.
    """

    key = value.strip().lower().replace("_", "-")
    key = key.replace("\u2011", "-")  # non-breaking hyphen
    key = key.replace("\u2013", "-").replace("\u2014", "-")
    key = key.replace(" ", "-")
    if key in JOB_TYPE_CATEGORIES:
        return JOB_TYPE_CATEGORIES[key]
    raise ValueError(f"Unknown job type: {value!r}")


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
    # Role-specific optional fields
    programming_languages: List[str] = []
    frameworks: List[str] = []
    tech_stack: List[str] = []
    code_quality_practices: List[str] = []
    development_methodology: str = ""
    target_markets: List[str] = []
    sales_quota: str = ""
    crm_tools: List[str] = []
    campaign_types: List[str] = []
    digital_marketing_platforms: List[str] = []
    required_certifications: List[str] = []
    shift_schedule: str = ""
    patient_ratio: str = ""
    board_certification: str = ""
    on_call_requirements: str = ""
    grade_level: str = ""
    teaching_license: str = ""
    design_software_tools: List[str] = []
    portfolio_url: str = ""
    project_management_methodologies: List[str] = []
    project_management_tools: List[str] = []
    stakeholder_types: List[str] = []
    budget_responsibility: str = ""
    machine_learning_frameworks: List[str] = []
    data_analysis_tools: List[str] = []
    data_visualization_tools: List[str] = []
    accounting_software: List[str] = []
    professional_certifications: List[str] = []
    reporting_standards: List[str] = []
    regulatory_frameworks: List[str] = []
    hr_software_tools: List[str] = []
    recruitment_channels: List[str] = []
    employee_engagement_strategies: List[str] = []
    engineering_software_tools: List[str] = []
    civil_project_types: List[str] = []
    site_visit_frequency: str = ""
    cuisine_specialties: List[str] = []
    kitchen_environment: str = ""
    menu_development_responsibility: str = ""


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


def _dedupe_across_fields(jd: VacalyserJD) -> VacalyserJD:
    """Remove duplicate content that appears in multiple fields.

    The first occurrence of a normalized text segment is kept and subsequent
    duplicates in later fields are cleared. Field order is determined by
    ``ALL_FIELDS`` so more specific fields earlier in the schema take priority.

    Args:
        jd: The vacancy profile to deduplicate.

    Returns:
        The deduplicated vacancy profile.
    """

    def _norm(text: str) -> str:
        return re.sub(r"\W+", " ", text).strip().lower()

    seen: set[str] = set()
    for field in ALL_FIELDS:
        value = getattr(jd, field)
        if field in LIST_FIELDS:
            filtered: List[str] = []
            for item in value:
                norm_item = _norm(item)
                if norm_item and norm_item not in seen:
                    seen.add(norm_item)
                    filtered.append(item)
            setattr(jd, field, filtered)
        else:
            norm_val = _norm(value)
            if norm_val in seen:
                setattr(jd, field, "")
            elif norm_val:
                seen.add(norm_val)

    return jd


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
    # 5) normalize categorical fields
    job_type_val = data.get("job_type", "")
    if job_type_val:
        data["job_type"] = _normalize_job_type(job_type_val)
    # 6) build model (extra keys ignored by BaseModel config)
    model = VacalyserJD(**data)
    return _dedupe_across_fields(model)
