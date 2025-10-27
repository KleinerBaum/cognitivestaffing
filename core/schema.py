"""Utilities for vacancy schemas (NeedAnalysis + RecruitingWizard)."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import ItemsView
from enum import StrEnum
from typing import Any, Dict, List, Mapping, Tuple, Union, get_args, get_origin

from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, RootModel, ValidationError, field_validator, model_validator

from models.need_analysis import NeedAnalysisProfile
from utils.normalization import normalize_profile

from .validators import deduplicate_preserve_order, ensure_canonical_keys
from llm.json_repair import repair_profile_payload


def _is_flag_enabled(value: str | None) -> bool:
    """Return ``True`` when the given feature flag value should be considered enabled."""

    if value is None:
        return False
    candidate = value.strip().lower()
    if not candidate:
        return False
    return candidate not in {"0", "false", "no", "off"}


# Feature flag guarding the RecruitingWizard schema rollout.
SCHEMA_WIZARD_V1 = _is_flag_enabled(os.getenv("SCHEMA_WIZARD_V1"))


class EmploymentType(StrEnum):
    """Supported employment contract types for the wizard schema."""

    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERN = "internship"
    FREELANCE = "freelance"


class WorkModel(StrEnum):
    """Supported work location policies for the wizard schema."""

    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    FLEXIBLE = "flexible"


class OnCallRequirement(StrEnum):
    """On-call expectations associated with a role."""

    NONE = "none"
    OPTIONAL = "optional"
    ROTATION = "rotation"
    REQUIRED = "required"


class SourceType(StrEnum):
    """Origin of a data point in the RecruitingWizard schema."""

    USER = "user"
    EXTRACT = "extract"
    WEB = "web"


class SourceAttribution(BaseModel):
    """Metadata describing how a specific field was populated."""

    model_config = ConfigDict(extra="forbid")

    source: SourceType = SourceType.USER
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_url: HttpUrl | None = None
    notes: str | None = None


class SourceMap(RootModel[dict[str, SourceAttribution]]):
    """Mapping of canonical dot-paths to their source metadata."""

    root: dict[str, SourceAttribution] = Field(default_factory=dict)

    def items(self) -> ItemsView[str, SourceAttribution]:  # type: ignore[override]
        return self.root.items()

    def get(self, key: str, default: SourceAttribution | None = None) -> SourceAttribution | None:
        return self.root.get(key, default)

    @model_validator(mode="after")
    def _ensure_canonical_paths(self) -> "SourceMap":
        if WIZARD_KEYS_CANONICAL:
            ensure_canonical_keys(self.root, WIZARD_KEYS_CANONICAL, context="source map")
        return self


class MissingFieldEntry(BaseModel):
    """Description for a missing or outstanding canonical field."""

    model_config = ConfigDict(extra="forbid")

    required: bool = True
    reason: str | None = None
    owner: str | None = None


class MissingFieldMap(RootModel[dict[str, MissingFieldEntry]]):
    """Mapping of canonical dot-paths to outstanding metadata."""

    root: dict[str, MissingFieldEntry] = Field(default_factory=dict)

    def items(self) -> ItemsView[str, MissingFieldEntry]:  # type: ignore[override]
        return self.root.items()

    def get(self, key: str, default: MissingFieldEntry | None = None) -> MissingFieldEntry | None:
        return self.root.get(key, default)

    @model_validator(mode="after")
    def _ensure_canonical_paths(self) -> "MissingFieldMap":
        if WIZARD_KEYS_CANONICAL:
            ensure_canonical_keys(self.root, WIZARD_KEYS_CANONICAL, context="missing field map")
        return self


class Company(BaseModel):
    """Top-level company details captured by the wizard."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    legal_name: str | None = None
    tagline: str | None = None
    mission: str | None = None
    headquarters: str | None = None
    locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    website: str | None = None
    values: list[str] = Field(default_factory=list)

    @field_validator("locations", "industries", "values", mode="before")
    @classmethod
    def _normalise_list(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Department(BaseModel):
    """Department or business unit context for the role."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    function: str | None = None
    leader_name: str | None = None
    leader_title: str | None = None
    strategic_goals: list[str] = Field(default_factory=list)

    @field_validator("strategic_goals", mode="before")
    @classmethod
    def _normalise_goals(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Team(BaseModel):
    """Team-level structure and collaboration hints."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    mission: str | None = None
    reporting_line: str | None = None
    headcount_current: int | None = None
    headcount_target: int | None = None
    collaboration_tools: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    @field_validator("collaboration_tools", "locations", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Role(BaseModel):
    """Role-specific details for the vacancy."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    purpose: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    work_model: WorkModel = WorkModel.HYBRID
    on_call: OnCallRequirement = OnCallRequirement.NONE
    reports_to: str | None = None
    seniority: str | None = None
    work_location: str | None = None

    @field_validator("outcomes", mode="before")
    @classmethod
    def _normalise_outcomes(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Tasks(BaseModel):
    """Key responsibilities and success metrics."""

    model_config = ConfigDict(extra="forbid")

    core: list[str] = Field(default_factory=list)
    secondary: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)

    @field_validator("core", "secondary", "success_metrics", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Skills(BaseModel):
    """Skill requirements grouped by criticality."""

    model_config = ConfigDict(extra="forbid")

    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    @field_validator("must_have", "nice_to_have", "certifications", "tools", "languages", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Benefits(BaseModel):
    """Compensation, perks, and support programmes."""

    model_config = ConfigDict(extra="forbid")

    salary_range: str | None = None
    currency: str | None = None
    bonus: str | None = None
    equity: str | None = None
    perks: list[str] = Field(default_factory=list)
    wellbeing: list[str] = Field(default_factory=list)
    relocation_support: str | None = None
    on_call: OnCallRequirement = OnCallRequirement.NONE

    @field_validator("perks", "wellbeing", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class InterviewProcess(BaseModel):
    """Structured overview of the interview stages."""

    model_config = ConfigDict(extra="forbid")

    steps: list[str] = Field(default_factory=list)
    interviewers: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    decision_timeline: str | None = None
    notes: str | None = None

    @field_validator("steps", "interviewers", "evaluation_criteria", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


class Summary(BaseModel):
    """Executive summary used across exports."""

    model_config = ConfigDict(extra="forbid")

    headline: str | None = None
    value_proposition: str | None = None
    culture_highlights: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    @field_validator("culture_highlights", "next_steps", mode="before")
    @classmethod
    def _normalise_lists(cls, value: object) -> list[str]:
        return deduplicate_preserve_order(value)


WIZARD_KEYS_CANONICAL: tuple[str, ...] = ()  # Populated after ``RecruitingWizard`` definition.


class RecruitingWizard(BaseModel):
    """Single source of truth schema for the Recruiting Wizard."""

    model_config = ConfigDict(extra="forbid")

    company: Company = Field(default_factory=Company)
    department: Department = Field(default_factory=Department)
    team: Team = Field(default_factory=Team)
    role: Role = Field(default_factory=Role)
    tasks: Tasks = Field(default_factory=Tasks)
    skills: Skills = Field(default_factory=Skills)
    benefits: Benefits = Field(default_factory=Benefits)
    interview_process: InterviewProcess = Field(default_factory=InterviewProcess)
    summary: Summary = Field(default_factory=Summary)
    sources: SourceMap = Field(default_factory=SourceMap)
    missing_fields: MissingFieldMap = Field(default_factory=MissingFieldMap)

    @model_validator(mode="after")
    def _validate_maps(self) -> "RecruitingWizard":
        if WIZARD_KEYS_CANONICAL:
            ensure_canonical_keys(self.sources.root, WIZARD_KEYS_CANONICAL, context="source map")
            ensure_canonical_keys(self.missing_fields.root, WIZARD_KEYS_CANONICAL, context="missing field map")
        return self


def is_wizard_schema_enabled() -> bool:
    """Return whether the RecruitingWizard schema flag is currently enabled."""

    env_value = os.getenv("SCHEMA_WIZARD_V1")
    if env_value is None:
        return SCHEMA_WIZARD_V1
    return _is_flag_enabled(env_value)


def _strip_optional(tp: Any) -> Any:
    """Remove ``Optional`` wrapper from a type annotation."""

    origin = get_origin(tp)
    if origin is Union:
        args = [arg for arg in get_args(tp) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def _collect_fields(model: type[BaseModel], prefix: str = "") -> Tuple[List[str], set[str], Dict[str, Any]]:
    """Recursively collect field paths, list-typed fields and types."""

    paths: List[str] = []
    list_fields: set[str] = set()
    types: Dict[str, Any] = {}
    for name, field in model.model_fields.items():
        tp = _strip_optional(field.annotation)
        path = f"{prefix}{name}"
        origin = get_origin(tp)
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            sub_paths, sub_lists, sub_types = _collect_fields(tp, f"{path}.")
            paths.extend(sub_paths)
            list_fields.update(sub_lists)
            types.update(sub_types)
        else:
            paths.append(path)
            types[path] = tp
            if origin in (list, List):
                list_fields.add(path)
    return paths, list_fields, types


RECRUITING_WIZARD_FIELDS, RECRUITING_WIZARD_LIST_FIELDS, RECRUITING_WIZARD_FIELD_TYPES = _collect_fields(
    RecruitingWizard
)
# WIZARD_KEYS_CANONICAL ensures all modules use the same canonical wizard dot-paths.  # CS_SCHEMA_PROPAGATE
WIZARD_KEYS_CANONICAL = tuple(sorted(RECRUITING_WIZARD_FIELDS))


ALL_FIELDS, LIST_FIELDS, FIELD_TYPES = _collect_fields(NeedAnalysisProfile)
# KEYS_CANONICAL exposes the canonical NeedAnalysisProfile dot-paths.  # CS_SCHEMA_PROPAGATE
KEYS_CANONICAL = tuple(sorted(ALL_FIELDS))
BOOL_FIELDS = {p for p, t in FIELD_TYPES.items() if t is bool}
INT_FIELDS = {p for p, t in FIELD_TYPES.items() if t is int}
FLOAT_FIELDS = {p for p, t in FIELD_TYPES.items() if t is float}

# Alias map for backward compatibility with legacy field names
# Using MappingProxyType to prevent accidental mutation.
logger = logging.getLogger(__name__)


ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "date_of_employment_start": "meta.target_start_date",
        "requirements.hard_skills": "requirements.hard_skills_required",
        "requirements.soft_skills": "requirements.soft_skills_required",
        "city": "location.primary_city",
        "location.city": "location.primary_city",
        "company.location.city": "location.primary_city",
        "company.location.country": "location.country",
        "company.location.country_code": "location.country",
        "company.hq": "company.hq_location",
        "brand name": "company.brand_name",
        "application deadline": "meta.application_deadline",
        "hr_contact_name": "company.contact_name",
        "hr_contact_email": "company.contact_email",
        "hr_contact_phone": "company.contact_phone",
        "hiring_manager_name": "process.hiring_manager_name",
        "hiring_manager_role": "process.hiring_manager_role",
        "reporting_manager_name": "position.reporting_manager_name",
        "role.title": "position.job_title",
        "role.department": "position.department",
        "role.team": "position.team_structure",
        "role.seniority": "position.seniority_level",
        "role.employment_type": "employment.job_type",
        "role.work_policy": "employment.work_policy",
        "role.travel_required_percent": "employment.travel_share",
        "role.relocation": "employment.relocation_support",
        "work_model": "employment.work_policy",
        "employment.work_model": "employment.work_policy",
        "company.tagline": "company.claim",
        "company.logo": "company.logo_url",
        "company.logoUrl": "company.logo_url",
        "company.brand_color_hex": "company.brand_color",
        "company.brand_colour": "company.brand_color",
        "responsibilities": "responsibilities.items",
        "compensation.min": "compensation.salary_min",
        "compensation.max": "compensation.salary_max",
        "compensation.currency_code": "compensation.currency",
        "compensation.periodicity": "compensation.period",
    }
)

_LIST_SPLIT_RE = re.compile(r"[,\n;•]+")
_TRUE_VALUES = {"true", "yes", "1", "ja"}
_FALSE_VALUES = {"false", "no", "0", "nein"}


def _to_mutable(data: Any) -> Any:
    if isinstance(data, Mapping):
        return {str(key): _to_mutable(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_to_mutable(item) for item in data]
    return data


def _find_key_casefold(container: Mapping[str, Any], key: str) -> str | None:
    needle = key.casefold()
    for candidate in container.keys():
        if candidate.casefold() == needle:
            return candidate
    return None


def _path_has_meaningful_value(data: Mapping[str, Any], path: str) -> bool:
    parts = path.split(".")
    cursor: Any = data
    for part in parts:
        if not isinstance(cursor, Mapping):
            return False
        actual = _find_key_casefold(cursor, part)
        if actual is None:
            return False
        cursor = cursor[actual]
    if cursor in (None, ""):
        return False
    if isinstance(cursor, (list, tuple, set, dict)):
        return bool(cursor)
    return True


def _pop_path_casefold(obj: dict[str, Any], path: str, default: Any) -> Any:
    parts = path.split(".")
    cursor: Any = obj
    parents: list[dict[str, Any]] = []
    keys: list[str] = []
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            return default
        actual = _find_key_casefold(cursor, part)
        if actual is None:
            return default
        parents.append(cursor)
        keys.append(actual)
        cursor = cursor[actual]
    if not isinstance(cursor, dict):
        return default
    last_key = _find_key_casefold(cursor, parts[-1])
    if last_key is None:
        return default
    return cursor.pop(last_key, default)


def _set_path(obj: dict[str, Any], path: str, value: Any, *, overwrite: bool = True) -> None:
    parts = path.split(".")
    cursor: Any = obj
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    if overwrite or not _path_has_meaningful_value(obj, path):
        cursor[parts[-1]] = value


def _apply_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    sentinel = object()
    for alias, target in ALIASES.items():
        value = _pop_path_casefold(payload, alias, sentinel)
        if value is sentinel:
            continue
        if isinstance(value, Mapping):
            last_part = target.split(".")[-1]
            if last_part in value:
                value = value[last_part]
        _set_path(payload, target, value, overwrite=False)
    return payload


def _filter_unknown_fields(data: dict[str, Any]) -> None:
    def _walk(node: dict[str, Any], prefix: str = "") -> None:
        for key in list(node.keys()):
            path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            value = node[key]
            if isinstance(value, dict):
                has_children = any(field.startswith(path + ".") for field in ALL_FIELDS)
                if path in ALL_FIELDS or has_children:
                    _walk(value, path)
                    if not value and path not in ALL_FIELDS:
                        del node[key]
                else:
                    del node[key]
            else:
                if path not in ALL_FIELDS:
                    del node[key]

    _walk(data)


def _coerce_scalar_types(data: dict[str, Any]) -> None:
    def _walk(node: dict[str, Any], prefix: str = "") -> None:
        for key, value in list(node.items()):
            path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            if isinstance(value, dict):
                _walk(value, path)
                continue
            if path in LIST_FIELDS and isinstance(value, str):
                cleaned = re.sub(r"^[^:]*:\s*", "", value)
                node[key] = [part.strip() for part in _LIST_SPLIT_RE.split(cleaned) if part.strip()]
            elif path in BOOL_FIELDS and isinstance(value, str):
                lower = value.strip().casefold()
                if lower in _TRUE_VALUES:
                    node[key] = True
                elif lower in _FALSE_VALUES:
                    node[key] = False
            elif path in INT_FIELDS and isinstance(value, str):
                match = re.search(r"-?\d+", value)
                if match:
                    node[key] = int(match.group())
            elif path in FLOAT_FIELDS and isinstance(value, str):
                match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", "."))
                if match:
                    node[key] = float(match.group())

    _walk(data)


def canonicalize_profile_payload(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a sanitized mapping ready for NeedAnalysisProfile validation."""

    if data is None:
        return {}
    mutable = _to_mutable(data)
    if not isinstance(mutable, dict):
        return {}
    payload = _apply_aliases(mutable)
    _filter_unknown_fields(payload)
    _coerce_scalar_types(payload)
    return payload


def coerce_and_fill(data: Mapping[str, Any] | None) -> NeedAnalysisProfile:
    """Validate ``data`` and ensure required fields are present.

    Incoming payloads are canonicalised so that alias keys, obvious type
    mismatches and stray fields are handled in a single place before validation.
    """

    payload = canonicalize_profile_payload(data)

    try:
        profile = NeedAnalysisProfile.model_validate(payload)
    except ValidationError as exc:
        repaired_payload = repair_profile_payload(payload, errors=exc.errors())
        if not repaired_payload:
            raise
        canonical_repaired = canonicalize_profile_payload(repaired_payload)
        try:
            profile = NeedAnalysisProfile.model_validate(canonical_repaired)
        except ValidationError:
            raise
        logger.info("Repaired NeedAnalysisProfile payload via JSON repair fallback.")
        payload = canonical_repaired

    return normalize_profile(profile)


def process_extracted_profile(raw_profile: Mapping[str, Any] | None) -> NeedAnalysisProfile:
    """Convert a raw extraction payload into a normalised profile."""

    return coerce_and_fill(raw_profile)


# Backwards compatibility aliases
CognitiveNeedsProfile = NeedAnalysisProfile
CognitiveNeedsJD = NeedAnalysisProfile  # pragma: no cover - legacy alias
