"""Pydantic models for the need analysis profile."""

from __future__ import annotations

import re
from typing import Any, ClassVar, List, Optional

from email_validator import EmailNotValidError, validate_email

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class Company(BaseModel):
    """Details about the hiring company."""

    model_config = ConfigDict(extra="forbid")

    _EMAIL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE
    )

    name: Optional[str] = None
    brand_name: Optional[str] = None
    industry: Optional[str] = None
    hq_location: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    mission: Optional[str] = None
    culture: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: EmailStr | None = None
    contact_phone: Optional[str] = None
    brand_keywords: Optional[str] = None

    @field_validator("contact_email", mode="before")
    @classmethod
    def _extract_first_email(cls, value: str | None) -> str | None:
        """Extract the first valid email address from a noisy input string."""

        if value is None:
            return None
        if isinstance(value, EmailStr):
            return str(value)
        if not isinstance(value, str):
            return None

        candidate_source = value.strip()
        if not candidate_source:
            return None

        match = cls._EMAIL_PATTERN.search(candidate_source)
        if not match:
            return None

        candidate = match.group(0)
        try:
            validated = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError:
            return None
        return validated.normalized.casefold()


class Position(BaseModel):
    """Information describing the open position."""

    model_config = ConfigDict(extra="forbid")

    job_title: Optional[str] = None
    seniority_level: Optional[str] = None
    department: Optional[str] = None
    team_structure: Optional[str] = None
    reporting_line: Optional[str] = None
    role_summary: Optional[str] = None
    occupation_label: Optional[str] = None
    occupation_uri: Optional[str] = None
    occupation_group: Optional[str] = None
    supervises: Optional[int] = None
    performance_indicators: Optional[str] = None
    decision_authority: Optional[str] = None
    key_projects: Optional[str] = None
    team_size: Optional[int] = None


class Location(BaseModel):
    """Primary location information for the role."""

    model_config = ConfigDict(extra="forbid")

    primary_city: Optional[str] = None
    country: Optional[str] = None
    onsite_ratio: Optional[str] = None


class Responsibilities(BaseModel):
    """Key responsibilities for the role."""

    model_config = ConfigDict(extra="forbid")

    items: List[str] = Field(default_factory=list)


class Requirements(BaseModel):
    """Required and optional skills and qualifications."""

    model_config = ConfigDict(extra="forbid")

    hard_skills_required: List[str] = Field(default_factory=list)
    hard_skills_optional: List[str] = Field(default_factory=list)
    soft_skills_required: List[str] = Field(default_factory=list)
    soft_skills_optional: List[str] = Field(default_factory=list)
    tools_and_technologies: List[str] = Field(default_factory=list)
    languages_required: List[str] = Field(default_factory=list)
    languages_optional: List[str] = Field(default_factory=list)
    certificates: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    language_level_english: Optional[str] = None

    @model_validator(mode="after")
    @classmethod
    def _sync_certificates(cls, values: "Requirements") -> "Requirements":
        """Keep ``certificates`` and ``certifications`` aligned."""

        combined: list[str] = []
        seen: set[str] = set()
        for source in (values.certifications, values.certificates):
            for item in source:
                cleaned = (item or "").strip()
                if not cleaned:
                    continue
                marker = cleaned.casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                combined.append(cleaned)
        values.certificates = combined.copy()
        values.certifications = combined.copy()
        return values


class Employment(BaseModel):
    """Employment contract details."""

    model_config = ConfigDict(extra="forbid")

    job_type: Optional[str] = None
    work_policy: Optional[str] = None
    contract_type: Optional[str] = None
    work_schedule: Optional[str] = None
    remote_percentage: Optional[int] = None
    contract_end: Optional[str] = None
    travel_required: Optional[bool] = None
    travel_share: Optional[int] = None
    travel_region_scope: Optional[str] = None
    travel_regions: List[str] = Field(default_factory=list)
    travel_continents: List[str] = Field(default_factory=list)
    travel_details: Optional[str] = None
    overtime_expected: Optional[bool] = None
    relocation_support: Optional[bool] = None
    relocation_details: Optional[str] = None
    visa_sponsorship: Optional[bool] = None
    security_clearance_required: Optional[bool] = None
    shift_work: Optional[bool] = None


class Compensation(BaseModel):
    """Salary and compensation information."""

    model_config = ConfigDict(extra="forbid")
    salary_provided: bool = False
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    variable_pay: Optional[bool] = None
    bonus_percentage: Optional[float] = None
    commission_structure: Optional[str] = None
    equity_offered: Optional[bool] = None
    benefits: List[str] = Field(default_factory=list)

    @field_validator("salary_provided", mode="before")
    @classmethod
    def _normalize_salary_provided(cls, value: Any) -> bool:
        """Coerce falsy placeholders into a real boolean value."""

        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return False
            lower = stripped.casefold()
            try:
                from utils.json_parse import FALSE_VALUES, TRUE_VALUES  # local import to avoid cycles

                if lower in TRUE_VALUES:
                    return True
                if lower in FALSE_VALUES:
                    return False
            except Exception:
                # Fallback if json_parse cannot be imported yet (e.g. circular init)
                pass
            if lower in {"none", "null", "n/a", "na"}:
                return False
            return bool(stripped)
        return bool(value)


class Stakeholder(BaseModel):
    """Person involved in the hiring process."""

    model_config = ConfigDict(extra="forbid")

    name: str
    role: str
    email: EmailStr | None = None
    primary: bool = False
    information_loop_phases: List[int] = Field(default_factory=list)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: EmailStr | str | None) -> str | None:
        """Clean stakeholder email addresses before ``EmailStr`` validation."""

        if value is None:
            return None
        if isinstance(value, EmailStr):
            return str(value)
        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate:
            return None

        try:
            validated = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError:
            return None
        return validated.normalized.casefold()


class Phase(BaseModel):
    """Single phase of the hiring process."""

    model_config = ConfigDict(extra="forbid")

    name: str
    interview_format: Optional[str] = None
    participants: List[str] = Field(default_factory=list)
    docs_required: Optional[str] = None
    assessment_tests: Optional[bool] = None
    timeframe: Optional[str] = None
    task_assignments: Optional[str] = None


class Process(BaseModel):
    """Information about the hiring process."""

    model_config = ConfigDict(extra="forbid")
    interview_stages: Optional[int] = None
    stakeholders: List[Stakeholder] = Field(default_factory=list)
    phases: List[Phase] = Field(default_factory=list)
    recruitment_timeline: Optional[str] = None
    process_notes: Optional[str] = None
    application_instructions: Optional[str] = None
    onboarding_process: Optional[str] = None


class Meta(BaseModel):
    """Miscellaneous metadata about the profile."""

    model_config = ConfigDict(extra="forbid")

    target_start_date: Optional[str] = None
    application_deadline: Optional[str] = None
    followups_answered: List[str] = Field(default_factory=list)


class NeedAnalysisProfile(BaseModel):
    """Aggregate need analysis profile model."""

    model_config = ConfigDict(extra="forbid")

    company: Company = Field(default_factory=Company)
    position: Position = Field(default_factory=Position)
    location: Location = Field(default_factory=Location)
    responsibilities: Responsibilities = Field(default_factory=Responsibilities)
    requirements: Requirements = Field(default_factory=Requirements)
    employment: Employment = Field(default_factory=Employment)
    compensation: Compensation = Field(default_factory=Compensation)
    process: Process = Field(default_factory=Process)
    meta: Meta = Field(default_factory=Meta)

    @field_validator("company", "position", mode="before")
    @classmethod
    def _ensure_present(cls, value: Any) -> dict | Company | Position:
        """Ensure nested objects are present."""
        return {} if value is None else value
