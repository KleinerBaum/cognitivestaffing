"""Pydantic models for the need analysis profile."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any


class Company(BaseModel):
    """Details about the hiring company."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    brand_name: Optional[str] = None
    industry: Optional[str] = None
    hq_location: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    mission: Optional[str] = None
    culture: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


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
    certifications: List[str] = Field(default_factory=list)
    language_level_english: Optional[str] = None


class Employment(BaseModel):
    """Employment contract details."""

    model_config = ConfigDict(extra="forbid")

    job_type: Optional[str] = None
    work_policy: Optional[str] = None
    contract_type: Optional[str] = None
    travel_required: Optional[bool] = None
    overtime_expected: Optional[bool] = None
    relocation_support: Optional[bool] = None
    visa_sponsorship: Optional[bool] = None
    security_clearance_required: Optional[bool] = None
    shift_work: Optional[bool] = None


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
