"""Pydantic schema definitions for Vacalyser job descriptions."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
