"""Pydantic models for the Vacalyser job description schema."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union, get_args, get_origin, Mapping

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field


# --- Teilmodelle ---


class Company(BaseModel):
    """Details about the hiring company."""

    model_config = ConfigDict(extra="forbid")

    name: str
    industry: Optional[str] = None
    hq_location: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    mission: Optional[str] = None
    culture: Optional[str] = None


class Location(BaseModel):
    """Primary location information for the role."""

    model_config = ConfigDict(extra="forbid")

    primary_city: Optional[str] = None
    country: Optional[str] = None
    onsite_ratio: Optional[str] = None


class Position(BaseModel):
    """Information describing the open position."""

    model_config = ConfigDict(extra="forbid")

    job_title: str
    seniority_level: Optional[str] = None
    department: Optional[str] = None
    team_structure: Optional[str] = None
    reporting_line: Optional[str] = None
    role_summary: Optional[str] = None
    # ESCO-Erweiterungen (optional)
    occupation_label: Optional[str] = None
    occupation_uri: Optional[str] = None
    occupation_group: Optional[str] = None


class Responsibilities(BaseModel):
    """List of key responsibilities for the role."""

    model_config = ConfigDict(extra="forbid")

    items: List[str] = Field(default_factory=list)


class Requirements(BaseModel):
    """Required skills and qualifications."""

    model_config = ConfigDict(extra="forbid")

    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    tools_and_technologies: List[str] = Field(default_factory=list)
    languages_required: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class Employment(BaseModel):
    """Employment contract details."""

    model_config = ConfigDict(extra="forbid")

    job_type: Optional[str] = None
    work_policy: Optional[str] = None
    travel_required: Optional[bool] = None
    relocation_support: Optional[bool] = None
    visa_sponsorship: Optional[bool] = None


class Compensation(BaseModel):
    """Salary and compensation information."""

    model_config = ConfigDict(extra="forbid")

    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    variable_pay: Optional[bool] = None
    equity_offered: Optional[bool] = None
    benefits: List[str] = Field(default_factory=list)


class Process(BaseModel):
    """Information about the hiring process."""

    model_config = ConfigDict(extra="forbid")

    interview_stages: Optional[int] = None
    process_notes: Optional[str] = None


class Meta(BaseModel):
    """Miscellaneous metadata about the vacancy."""

    model_config = ConfigDict(extra="forbid")

    target_start_date: Optional[str] = None
    application_deadline: Optional[str] = None


# --- Aggregat (Top-Level) ---


class VacalyserJD(BaseModel):
    """Aggregate job description model for Vacalyser."""

    model_config = ConfigDict(extra="forbid")

    company: Company
    position: Position
    # OPTION A (strikt optional, bleibt None bis gesetzt):
    location: Optional[Location] = None
    responsibilities: Optional[Responsibilities] = None
    requirements: Optional[Requirements] = None
    employment: Optional[Employment] = None
    compensation: Optional[Compensation] = None
    process: Optional[Process] = None
    meta: Optional[Meta] = None

    # OPTION B (auto-init leere Teilmodelle statt None):
    # location: Location = Field(default_factory=Location)
    # responsibilities: Responsibilities = Field(default_factory=Responsibilities)
    # requirements: Requirements = Field(default_factory=Requirements)
    # employment: Employment = Field(default_factory=Employment)
    # compensation: Compensation = Field(default_factory=Compensation)
    # process: Process = Field(default_factory=Process)
    # meta: Meta = Field(default_factory=Meta)


# Hilfsfunktion: „coerce_and_fill“ wie in deiner Extraktion referenziert
def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``updates`` into ``base`` and return the result."""

    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def coerce_and_fill(data: dict[str, Any]) -> VacalyserJD:
    """Validate ``data`` and ensure required fields are present.

    The function inserts minimal default structures (e.g. empty company name and
    job title) before validating the payload against :class:`VacalyserJD`.

    Args:
        data: Raw dictionary returned from the LLM.

    Returns:
        VacalyserJD: Validated model instance with defaults applied.
    """

    defaults: dict[str, Any] = {"company": {"name": ""}, "position": {"job_title": ""}}
    merged = _deep_merge(defaults, data or {})
    return VacalyserJD.model_validate(merged)


def _strip_optional(tp: Any) -> Any:
    """Remove ``Optional`` wrapper from a type annotation."""

    origin = get_origin(tp)
    if origin is Union:
        args = [arg for arg in get_args(tp) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def _collect_fields(
    model: type[BaseModel], prefix: str = ""
) -> Tuple[List[str], set[str]]:
    """Recursively collect field paths and list-typed fields."""

    paths: List[str] = []
    list_fields: set[str] = set()
    for name, field in model.model_fields.items():
        tp = _strip_optional(field.annotation)
        path = f"{prefix}{name}"
        origin = get_origin(tp)
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            sub_paths, sub_lists = _collect_fields(tp, f"{path}.")
            paths.extend(sub_paths)
            list_fields.update(sub_lists)
        else:
            paths.append(path)
            if origin in (list, List):
                list_fields.add(path)
    return paths, list_fields


ALL_FIELDS, LIST_FIELDS = _collect_fields(VacalyserJD)

# Empty alias map retained for compatibility with older code paths
# Using MappingProxyType to prevent accidental mutation.
ALIASES: Mapping[str, str] = MappingProxyType({})
