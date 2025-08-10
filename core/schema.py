"""
Vacalyser – canonical extraction schema and coercion utilities.

Implements:
- CS-SCH-01: Typed schema (Pydantic)
- CS-SCH-02: Constants for field lists
- CS-SCH-03: Normalizer & default filler
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

# --- Pydantic v2/v1 compatibility -------------------------------------------
try:
    from pydantic import BaseModel, Field  # type: ignore
    from pydantic import ConfigDict  # v2
    _HAS_V2 = True
except Exception:  # pragma: no cover
    from pydantic import BaseModel, Field  # type: ignore
    ConfigDict = None  # type: ignore
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
# Expectation: len(ALL_FIELDS) == 22
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

# Convenience set of string-typed fields
STRING_FIELDS = set(ALL_FIELDS) - set(LIST_FIELDS)

# Backward-compatibility aliases (input normalization only).
ALIASES: Dict[str, str] = {
    "requirements": "qualifications",
    "contract_type": "job_type",
    "tasks": "responsibilities",
}


# ---- Pydantic Base with "ignore extra" behavior (v2/v1) ---------------------
if _HAS_V2:
    class _BaseModel(BaseModel):
        model_config = ConfigDict(extra="ignore")
else:  # pragma: no cover
    class _BaseModel(BaseModel):
        class Config:
            extra = "ignore"


class VacalyserJD(_BaseModel):
    """
    Canonical extraction object returned by the LLM (after validation/coercion).

    All string fields default to "", all list fields default to [].
    Always include every key (even if empty) to keep the shape stable.
    """
    schema_version: str = Field(default=SCHEMA_VERSION)

    # --- strings ---
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

    # --- lists ---
    responsibilities: List[str] = []
    hard_skills: List[str] = []
    soft_skills: List[str] = []
    certifications: List[str] = []
    benefits: List[str] = []
    languages_required: List[str] = []
    tools_and_technologies: List[str] = []


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if not isinstance(x, str):
            x = str(x)
        val = x.strip()
        if not val:
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def coerce_and_fill(d: Dict[str, Any]) -> VacalyserJD:
    """
    Normalize an arbitrary dict into a validated VacalyserJD.

    Steps:
      1) Apply alias mapping (e.g., "tasks" -> "responsibilities").
      2) Insert any missing keys ('' for strings, [] for lists).
      3) Coerce list fields to List[str], dedupe while preserving order.
      4) Coerce string fields to str and strip whitespace.
      5) Ignore unknown extra keys.

    Returns:
        VacalyserJD
    """
    if d is None:
        d = {}

    data: Dict[str, Any] = dict(d)

    # 1) apply aliases
    for old, new in ALIASES.items():
        if old in data and new not in data:
            data[new] = data.pop(old)

    # 2) insert missing with defaults
    for k in ALL_FIELDS:
        if k not in data:
            data[k] = [] if k in LIST_FIELDS else ""

    # 3) coerce list fields
    for k in LIST_FIELDS:
        v = data.get(k, [])
        if isinstance(v, str):
            # Split common delimiters → lines, commas, semicolons
            parts = []
            for chunk in v.replace("\r\n", "\n").split("\n"):
                parts.extend([p for p in chunk.split(",")])
            v = parts
        elif not isinstance(v, list):
            v = [v]
        data[k] = _dedupe_preserve_order(v)

    # 4) coerce string fields
    for k in STRING_FIELDS:
        v = data.get(k, "")
        if v is None:
            v = ""
        data[k] = str(v).strip()

    # 5) construct model (pydantic ignores extras)
    return VacalyserJD(**data)


__all__ = [
    "SCHEMA_VERSION",
    "ALL_FIELDS",
    "LIST_FIELDS",
    "STRING_FIELDS",
    "ALIASES",
    "VacalyserJD",
    "coerce_and_fill",
]
