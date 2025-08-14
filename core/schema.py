from __future__ import annotations
from typing import Any, Dict, List
import re

try:
    from pydantic import BaseModel, Field
    from pydantic import ConfigDict  # Pydantic v2

    _HAS_V2 = True
except ImportError:
    from pydantic import BaseModel, Field  # type: ignore

    ConfigDict = None
    _HAS_V2 = False

SCHEMA_VERSION = "v2.1"


# Define nested models for each schema group (priority 1-3 fields only)
class Company(BaseModel):
    name: str = ""
    industry: str = ""
    hq_location: str = ""
    size: str = ""
    website: str = ""
    mission: str = ""
    culture: str = ""


class Compensation(BaseModel):
    salary_currency: str = "EUR"
    salary_max: int = 0
    salary_min: int = 0
    salary_period: str = "year"
    salary_provided: bool = True
    benefits: List[str] = []
    bonus_target_percent: int = 0
    variable_pay: bool = False
    commission_structure: str = ""
    equity_offered: bool = False
    equity_range: str = ""
    equity_type: str = ""
    healthcare_plan: str = ""
    paid_time_off_days: int = 0
    parental_leave_weeks: int = 0
    pension_plan: str = ""
    sick_days: int = 0


class ContactPerson(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    notify_stages: List[str] = []


class Contacts(BaseModel):
    hiring_manager: ContactPerson = ContactPerson()
    hr: ContactPerson = ContactPerson()
    recruiter: ContactPerson = ContactPerson()
    additional_notes: str = ""


class Employment(BaseModel):
    job_type: str = ""
    work_policy: str = "Onsite"
    employment_term: str = ""
    onsite_days_per_week: int = 0
    remote_percentage: int = 0
    travel_required: bool = False
    work_schedule: str = ""
    clearance_level: str = ""
    office_locations_allowed: List[str] = []
    overtime_expected: bool = False
    overtime_policy: str = ""
    relocation_support: bool = False
    remote_timezone_overlap_hours: int = 0
    security_clearance_required: bool = False
    shift_patterns: List[str] = []
    shift_work: bool = False
    travel_frequency: str = ""
    travel_percentage: int = 0
    travel_regions: List[str] = []
    visa_sponsorship: bool = False
    visa_types_supported: List[str] = []
    work_hours_per_week: int = 0


class Location(BaseModel):
    country: str = ""
    primary_city: str = ""
    geo_eligibility_countries: List[str] = []
    region_state: str = ""
    timezone: str = ""


class Meta(BaseModel):
    job_posting_url: str = ""
    date_posted: str = ""
    date_retrieved: str = ""
    source_platform: str = ""
    source_type: str = ""
    # parsed_by_model and schema_version are not included (schema_version is top-level)


class Position(BaseModel):
    job_title: str = ""
    seniority_level: str = ""
    department: str = ""
    management_scope: str = ""
    reporting_line: str = ""
    role_summary: str = ""
    application_deadline: str = ""
    business_unit: str = ""
    direct_reports_count: int = 0
    function: str = ""
    role_objectives: str = ""
    target_start_date: str = ""
    team_roles: List[str] = []
    team_size: int = 0
    team_structure: str = ""
    occupation_esco_code: str = ""
    occupation_esco_title: str = ""
    cross_functional: bool = False
    job_family: str = ""


class Requirements(BaseModel):
    hard_skills: List[str] = []
    education_level: str = ""
    languages_required: List[str] = []
    soft_skills: List[str] = []
    tools_and_technologies: List[str] = []
    years_experience_min: int = 0
    background_check_required: bool = False
    certifications: List[str] = []
    fields_of_study: List[str] = []
    portfolio_required: bool = False
    portfolio_url: str = ""
    reference_check_required: bool = False
    language_level_english: str = ""
    language_level_german: str = ""
    years_experience_preferred: int = 0


class Responsibilities(BaseModel):
    items: List[str] = []
    top3: List[str] = []


class Process(BaseModel):
    application_method: str = ""
    candidate_documents_required: List[str] = []
    start_date_target: str = ""
    application_email: str = ""
    application_url: str = ""
    has_technical_test: bool = False
    interviewers_panel: List[str] = []
    interview_stages: int = 0
    process_notes: str = ""


class Analytics(BaseModel):
    esco_missing_skill_count: int = 0
    skill_coverage_percent: int = 0
    benefits_completeness_score: int = 0
    inclusive_language_flags: List[str] = []
    jd_readability_score: float = 0.0
    legal_risk_notes: str = ""
    salary_benchmark_percentile: int = 0


# Base model configuration to ignore unknown fields
if _HAS_V2:

    class _BaseModel(BaseModel):
        model_config = ConfigDict(extra="ignore")

else:

    class _BaseModel(BaseModel):
        class Config:
            extra = "ignore"


class VacalyserJD(_BaseModel):
    """Canonical job description model (Vacalyzer v2.1)."""

    schema_version: str = Field(default=SCHEMA_VERSION)
    company: Company = Field(default_factory=Company)
    compensation: Compensation = Field(default_factory=Compensation)
    contacts: Contacts = Field(default_factory=Contacts)
    employment: Employment = Field(default_factory=Employment)
    location: Location = Field(default_factory=Location)
    meta: Meta = Field(default_factory=Meta)
    position: Position = Field(default_factory=Position)
    requirements: Requirements = Field(default_factory=Requirements)
    responsibilities: Responsibilities = Field(default_factory=Responsibilities)
    process: Process = Field(default_factory=Process)
    analytics: Analytics = Field(default_factory=Analytics)


# Define list of all fields (dot notation) for priority 1-3 fields
ALL_FIELDS: List[str] = [
    # Company fields
    "company.name",
    "company.industry",
    "company.hq_location",
    "company.size",
    "company.website",
    "company.mission",
    "company.culture",
    # Position fields
    "position.job_title",
    "position.seniority_level",
    "position.department",
    "position.management_scope",
    "position.reporting_line",
    "position.role_summary",
    "position.application_deadline",
    "position.business_unit",
    "position.direct_reports_count",
    "position.function",
    "position.role_objectives",
    "position.target_start_date",
    "position.team_roles",
    "position.team_size",
    "position.team_structure",
    "position.occupation_esco_code",
    "position.occupation_esco_title",
    "position.cross_functional",
    "position.job_family",
    # Compensation fields
    "compensation.salary_currency",
    "compensation.salary_min",
    "compensation.salary_max",
    "compensation.salary_period",
    "compensation.salary_provided",
    "compensation.benefits",
    "compensation.bonus_target_percent",
    "compensation.variable_pay",
    "compensation.commission_structure",
    "compensation.equity_offered",
    "compensation.equity_range",
    "compensation.equity_type",
    "compensation.healthcare_plan",
    "compensation.paid_time_off_days",
    "compensation.parental_leave_weeks",
    "compensation.pension_plan",
    "compensation.sick_days",
    # Employment fields
    "employment.job_type",
    "employment.work_policy",
    "employment.employment_term",
    "employment.onsite_days_per_week",
    "employment.remote_percentage",
    "employment.travel_required",
    "employment.work_schedule",
    "employment.clearance_level",
    "employment.office_locations_allowed",
    "employment.overtime_expected",
    "employment.overtime_policy",
    "employment.relocation_support",
    "employment.remote_timezone_overlap_hours",
    "employment.security_clearance_required",
    "employment.shift_patterns",
    "employment.shift_work",
    "employment.travel_frequency",
    "employment.travel_percentage",
    "employment.travel_regions",
    "employment.visa_sponsorship",
    "employment.visa_types_supported",
    "employment.work_hours_per_week",
    # Location fields
    "location.country",
    "location.primary_city",
    "location.geo_eligibility_countries",
    "location.region_state",
    "location.timezone",
    # Contacts fields
    "contacts.hiring_manager.name",
    "contacts.hiring_manager.email",
    "contacts.hiring_manager.phone",
    "contacts.hiring_manager.notify_stages",
    "contacts.hr.name",
    "contacts.hr.email",
    "contacts.hr.phone",
    "contacts.hr.notify_stages",
    "contacts.recruiter.name",
    "contacts.recruiter.email",
    "contacts.recruiter.phone",
    "contacts.recruiter.notify_stages",
    "contacts.additional_notes",
    # Requirements fields
    "requirements.hard_skills",
    "requirements.education_level",
    "requirements.languages_required",
    "requirements.soft_skills",
    "requirements.tools_and_technologies",
    "requirements.years_experience_min",
    "requirements.background_check_required",
    "requirements.certifications",
    "requirements.fields_of_study",
    "requirements.portfolio_required",
    "requirements.portfolio_url",
    "requirements.reference_check_required",
    "requirements.language_level_english",
    "requirements.language_level_german",
    "requirements.years_experience_preferred",
    # Responsibilities fields
    "responsibilities.items",
    "responsibilities.top3",
]
# List fields set (all keys in ALL_FIELDS that are list-typed)
LIST_FIELDS: set[str] = {
    # from Company: (none are lists in pr1-3)
    # from Position: team_roles is a list
    "position.team_roles",
    # from Compensation: benefits is a list
    "compensation.benefits",
    # from Contacts: notify_stages lists
    "contacts.hiring_manager.notify_stages",
    "contacts.hr.notify_stages",
    "contacts.recruiter.notify_stages",
    # from Employment: office_locations_allowed, shift_patterns, travel_regions, visa_types_supported
    "employment.office_locations_allowed",
    "employment.shift_patterns",
    "employment.travel_regions",
    "employment.visa_types_supported",
    # from Location: geo_eligibility_countries
    "location.geo_eligibility_countries",
    # from Requirements: hard_skills, languages_required, soft_skills, tools_and_technologies, certifications, fields_of_study
    "requirements.hard_skills",
    "requirements.languages_required",
    "requirements.soft_skills",
    "requirements.tools_and_technologies",
    "requirements.certifications",
    "requirements.fields_of_study",
    # from Responsibilities: items, top3
    "responsibilities.items",
    "responsibilities.top3",
}
STRING_FIELDS: set[str] = set(ALL_FIELDS) - LIST_FIELDS

# Aliases for backward compatibility (map old keys to new keys)
ALIASES: Dict[str, str] = {
    "company_name": "company.name",
    "job_title": "position.job_title",
    "location": "location.primary_city",
    "contract_type": "employment.job_type",
    "remote_policy": "employment.work_policy",
    "experience_level": "position.seniority_level",
    "start_date": "position.target_start_date",
    "tasks": "responsibilities.items",
    "travel_required": "employment.travel_required",
    "tools_technologies": "requirements.tools_and_technologies",
    "hiring_manager_phone": "contacts.hiring_manager.phone",
    "hr_phone": "contacts.hr.phone",
    "recruiter_phone": "contacts.recruiter.phone",
    "english_level": "requirements.language_level_english",
    "german_level": "requirements.language_level_german",
    "company_mission": "company.mission",
    "company_culture": "company.culture",
    # Note: "qualifications" field is removed; no direct alias for "requirements" group as a whole.
}

# Canonical normalization for job_type values (unchanged from v1)
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
    "apprenticeship": "Apprenticeship",
    "freelance": "Freelance",
}


def _normalize_job_type(value: str) -> str:
    key = value.strip().lower().replace("_", "-")
    key = key.replace("\u2011", "-")  # non-breaking hyphen
    key = key.replace("\u2013", "-").replace("\u2014", "-")
    key = key.replace(" ", "-")
    if key in JOB_TYPE_CATEGORIES:
        return JOB_TYPE_CATEGORIES[key]
    # If not recognized, return original capitalized
    return value


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    """Remove duplicates from a list while preserving order and stripping whitespace."""
    seen = set()
    result: List[str] = []
    for x in items:
        val = str(x).strip()
        if not val:
            continue
        if val not in seen:
            seen.add(val)
            result.append(val)
    return result


def _dedupe_across_fields(jd: VacalyserJD) -> VacalyserJD:
    """
    Remove duplicate text appearing in multiple fields (for nested schema).
    The first occurrence of a normalized text segment is kept; subsequent occurrences in later fields are cleared.
    Field order follows ALL_FIELDS.
    """

    def _norm(text: Any) -> str:
        """Normalize any value to lowercase alphanumeric string for dedupe."""
        return re.sub(r"\W+", " ", str(text)).strip().lower()

    def _get(path: str) -> Any:
        cursor: Any = jd
        for part in path.split("."):
            cursor = getattr(cursor, part)
        return cursor

    def _set(path: str, value: Any) -> None:
        cursor: Any = jd
        parts = path.split(".")
        for part in parts[:-1]:
            cursor = getattr(cursor, part)
        setattr(cursor, parts[-1], value)

    defaults = VacalyserJD()
    seen: set[str] = set()
    for field in ALL_FIELDS:
        val = _get(field)
        if field in LIST_FIELDS:
            filtered: List[str] = []
            for item in val:
                norm_item = _norm(item)
                if norm_item and norm_item not in seen:
                    seen.add(norm_item)
                    filtered.append(item)
            _set(field, filtered)
        else:
            norm_val = _norm(val)
            if norm_val in seen and norm_val:
                # duplicate found, reset to default value
                cursor: Any = defaults
                for part in field.split("."):
                    cursor = getattr(cursor, part)
                _set(field, cursor)
            elif norm_val:
                seen.add(norm_val)
    return jd


def coerce_and_fill(data: Dict[str, Any]) -> VacalyserJD:
    """
    Normalize an arbitrary dict into a validated VacalyserJD instance.
    Steps:
      1) Flatten nested dicts into dot keys and apply alias mapping.
      2) Insert missing keys ('' or [] defaults for each expected field).
      3) Coerce list fields to List[str], splitting strings on newlines/commas.
      4) Coerce string fields to str and strip whitespace.
      5) Normalize categorical fields (e.g., job_type).
      6) Build VacalyserJD model and deduplicate overlapping content.
    """
    if data is None:
        data = {}
    # 1) flatten nested structures and apply aliases
    flat: Dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, dict):
            for subkey, subval in val.items():
                flat[f"{key}.{subkey}"] = subval
        else:
            flat[key] = val
    # apply alias mapping
    for old, new in ALIASES.items():
        if old not in flat:
            continue
        old_val = flat.pop(old)
        if new in flat:
            if new in LIST_FIELDS:
                new_val = flat[new]
                if not isinstance(new_val, list):
                    new_val = [new_val]
                if isinstance(old_val, list):
                    combined = new_val + old_val
                else:
                    combined = new_val + [old_val]
                flat[new] = combined
            else:
                # Canonical value already present; discard alias value
                pass
        else:
            flat[new] = old_val
    data = flat
    # 2) insert missing keys with defaults from the canonical model
    #    This preserves numeric/boolean defaults instead of generic strings.
    _defaults = VacalyserJD()
    for key in ALL_FIELDS:
        if key in data:
            continue
        cursor: Any = _defaults
        for part in key.split("."):
            cursor = getattr(cursor, part)
        data[key] = cursor
    # 3) coerce list fields
    for key in LIST_FIELDS:
        value = data.get(key, [])
        if isinstance(value, str):
            # Split on newlines and commas/semicolons for list fields
            parts: List[str] = []
            for chunk in value.replace("\r\n", "\n").split("\n"):
                for piece in chunk.split(","):
                    if piece:
                        parts.append(piece.strip())
            value = parts
        elif value is None:
            value = []
        elif not isinstance(value, list):
            value = [value]
        data[key] = _dedupe_preserve_order([str(x) for x in value])
    # 4) coerce string fields
    for key in STRING_FIELDS:
        val = data.get(key, "")
        if val is None:
            val = ""
        data[key] = str(val).strip()
    # 5) normalize categorical fields
    job_type_val = data.get("employment.job_type", "")
    if job_type_val:
        data["employment.job_type"] = _normalize_job_type(job_type_val)
    # 6) build nested model
    nested: Dict[str, Any] = {}
    for key, val in data.items():
        if "." in key:
            group, subfield = key.split(".", 1)
            if group not in nested:
                nested[group] = {}
            nested[group][subfield] = val
        else:
            nested[key] = val
    model = VacalyserJD(**nested)
    return _dedupe_across_fields(model)
