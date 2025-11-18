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
    HttpUrl,
    field_validator,
    model_validator,
)

from core.normalization import sanitize_optional_url_value
from core.validation import is_placeholder
from utils.normalization import (
    normalize_company_size,
    normalize_phone_number,
    normalize_website_url,
)


class Company(BaseModel):
    """Details about the hiring company and its branding metadata."""

    model_config = ConfigDict(extra="forbid")

    _EMAIL_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

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
    logo_url: HttpUrl | None = None
    brand_color: Optional[str] = None
    claim: Optional[str] = None
    benefits: List[str] = Field(default_factory=list)

    @field_validator("logo_url", mode="before")
    @classmethod
    def _normalise_logo_url(cls, value: object) -> object | None:
        """Treat empty strings or whitespace-only inputs as ``None``."""

        sanitized = sanitize_optional_url_value(value)
        return sanitized

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

    @field_validator("size", mode="before")
    @classmethod
    def _normalise_size(cls, value: object) -> Optional[str]:
        """Normalise the employee count representation when determinable."""

        if value is None:
            return None
        if isinstance(value, str):
            normalized = normalize_company_size(value)
            if normalized:
                return normalized
            cleaned = value.strip()
            return cleaned or None
        return value  # type: ignore[return-value]

    @field_validator("website", mode="before")
    @classmethod
    def _normalise_website(cls, value: object) -> Optional[str]:
        """Ensure company websites use a canonical HTTPS format."""

        sanitized = sanitize_optional_url_value(value)
        if sanitized is None:
            return None
        normalized = normalize_website_url(sanitized)
        return normalized

    @field_validator("contact_phone", mode="before")
    @classmethod
    def _normalise_contact_phone(cls, value: object) -> Optional[str]:
        """Normalise contact phone numbers to a stable representation."""

        if value is None:
            return None
        normalized = normalize_phone_number(value if isinstance(value, str) else str(value))
        return normalized

    @field_validator("brand_color", mode="before")
    @classmethod
    def _normalise_brand_color(cls, value: object) -> Optional[str]:
        """Ensure brand colours are stored as uppercase hex values with ``#``."""

        if value is None:
            return None
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return None
            upper = candidate.upper()
            if re.fullmatch(r"#?[0-9A-F]{6}", upper):
                return upper if upper.startswith("#") else f"#{upper}"
            return candidate
        return value  # type: ignore[return-value]


class Position(BaseModel):
    """Information describing the open position."""

    model_config = ConfigDict(extra="forbid")

    job_title: Optional[str] = None
    seniority_level: Optional[str] = None
    team_structure: Optional[str] = None
    reporting_line: Optional[str] = None
    reporting_manager_name: Optional[str] = None
    role_summary: Optional[str] = None
    occupation_label: Optional[str] = None
    occupation_uri: Optional[str] = None
    occupation_group: Optional[str] = None
    supervises: Optional[int] = None
    performance_indicators: Optional[str] = None
    decision_authority: Optional[str] = None
    key_projects: Optional[str] = None
    team_size: Optional[int] = None
    customer_contact_required: Optional[bool] = None
    customer_contact_details: Optional[str] = None


class Department(BaseModel):
    """Department context for the open role."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    function: Optional[str] = None
    leader_name: Optional[str] = None
    leader_title: Optional[str] = None
    strategic_goals: Optional[str] = None


class Team(BaseModel):
    """Team context information for the role."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    mission: Optional[str] = None
    reporting_line: Optional[str] = None
    headcount_current: Optional[int] = None
    headcount_target: Optional[int] = None
    collaboration_tools: Optional[str] = None
    locations: Optional[str] = None


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
    background_check_required: Optional[bool] = None
    portfolio_required: Optional[bool] = None
    reference_check_required: Optional[bool] = None

    @model_validator(mode="after", skip_on_failure=True)
    def _sync_certificates(self) -> "Requirements":
        """Keep ``certificates`` and ``certifications`` aligned."""

        combined: list[str] = []
        seen: set[str] = set()
        for source in (self.certifications, self.certificates):
            for item in source:
                cleaned = (item or "").strip()
                if not cleaned:
                    continue
                marker = cleaned.casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                combined.append(cleaned)
        self.certificates = combined.copy()
        self.certifications = combined.copy()
        return self


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
            if is_placeholder(stripped):
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
    hiring_manager_name: Optional[str] = None
    hiring_manager_role: Optional[str] = None


class Meta(BaseModel):
    """Miscellaneous metadata about the profile."""

    model_config = ConfigDict(extra="forbid")

    target_start_date: Optional[str] = None
    application_deadline: Optional[str] = None
    followups_answered: List[str] = Field(default_factory=list)


class NeedAnalysisProfile(BaseModel):
    """Aggregate need analysis profile model with normalised sub-sections.

    Instances are produced via `core.schema.coerce_and_fill`, which applies
    schema aliases, triggers OpenAI-backed JSON repair, and calls
    `normalize_profile` so every consumer receives harmonised location data,
    deduplicated skill lists, and optional branding fields.
    """

    model_config = ConfigDict(extra="forbid")

    company: Company = Field(default_factory=Company)
    position: Position = Field(default_factory=Position)
    department: Department = Field(default_factory=Department)
    team: Team = Field(default_factory=Team)
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
