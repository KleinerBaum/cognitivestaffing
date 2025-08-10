"""Pydantic schema definitions for Vacalyser job descriptions."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Constants -----------------------------------------------------------------

# Field names in :class:`VacalyserJD` order.
ALL_FIELDS: list[str] = [
    "schema_version",
    "job_title",
    "company_name",
    "location",
    "industry",
    "job_type",
    "remote_policy",
    "travel_required",
    "role_summary",
    "qualifications",
    "salary_range",
    "reporting_line",
    "target_start_date",
    "team_structure",
    "application_deadline",
    "seniority_level",
    "responsibilities",
    "hard_skills",
    "soft_skills",
    "certifications",
    "benefits",
    "languages_required",
    "tools_and_technologies",
]

# Set of list-type fields in :class:`VacalyserJD`.
LIST_FIELDS: set[str] = {
    "responsibilities",
    "hard_skills",
    "soft_skills",
    "certifications",
    "benefits",
    "languages_required",
    "tools_and_technologies",
}


# Aliases for backward compatibility of field names.
ALIASES = {
    "requirements": "qualifications",
    "contract_type": "job_type",
    "tasks": "responsibilities",
}


class VacalyserJD(BaseModel):
    """Schema for extracted job description data.

    Attributes:
        schema_version: Version of this schema.
        job_title: Title of the job role.
        company_name: Name of the hiring company.
        location: Job location.
        industry: Industry classification of the job.
        job_type: Employment type (e.g., full-time).
        remote_policy: Remote work policy.
        travel_required: Travel requirements for the role.
        role_summary: Brief summary of the role.
        qualifications: Required qualifications.
        salary_range: Offered salary range.
        reporting_line: Reporting structure for the role.
        target_start_date: Desired start date.
        team_structure: Description of the team structure.
        application_deadline: Deadline for applications.
        seniority_level: Seniority level of the position.
        responsibilities: List of role responsibilities.
        hard_skills: List of hard skills required.
        soft_skills: List of soft skills required.
        certifications: Relevant certifications.
        benefits: Offered benefits.
        languages_required: Languages required for the role.
        tools_and_technologies: Tools and technologies used.
    """

    schema_version: str = Field(default="v1.0")
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

    responsibilities: list[str] = Field(default_factory=list)
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    languages_required: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)


def coerce_and_fill(d: dict) -> VacalyserJD:
    """Normalize raw dictionaries to :class:`VacalyserJD`.

    Missing keys are filled with defaults (empty string or list). Values for
    list-type fields are coerced into lists, trimmed for surrounding
    whitespace and deduplicated.

    Args:
        d: Partial job description data.

    Returns:
        A fully populated :class:`VacalyserJD` instance.
    """

    payload: dict[str, object] = dict(d)

    for alias, target in ALIASES.items():
        if alias in payload and target not in payload:
            payload[target] = payload[alias]

    result: dict[str, object] = {}
    for field in ALL_FIELDS:
        value = payload.get(field, [] if field in LIST_FIELDS else "")

        if field in LIST_FIELDS:
            if value is None:
                value = []
            if not isinstance(value, list):
                value = [value]

            cleaned: list[str] = []
            seen: set[str] = set()
            for item in value:
                item = str(item).strip()
                if item and item not in seen:
                    cleaned.append(item)
                    seen.add(item)
            result[field] = cleaned
        else:
            if value is None:
                value = ""
            result[field] = str(value).strip()

    return VacalyserJD(**result)
